"""End-to-end pipeline: fetch, parse, normalize, persist, and report."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from scraper_pipeline.browser import BrowserFetcher
from scraper_pipeline.config import FIXTURE_DIR, TARGETS, Settings, Target, get_settings
from scraper_pipeline.fetch import HttpFetcher
from scraper_pipeline.monitoring import JsonLogger, RunMetrics, new_run_id
from scraper_pipeline.normalize import deduplicate, normalize_books, normalize_quotes
from scraper_pipeline.parse import PARSERS
from scraper_pipeline.storage import DuckDBWarehouse, write_parquet

NORMALIZERS = {"books": normalize_books, "quotes": normalize_quotes}
OFFLINE_FIXTURES = {"books": "books_page1.html", "quotes": "quotes_js_rendered.html"}
BROWSER_WAIT_SELECTORS = {"quotes": "div.quote"}


@dataclass
class RunReport:
    """Summary of a completed pipeline run."""

    run_id: str
    source_counts: dict[str, int]
    metrics: RunMetrics
    warehouse_path: Path
    parquet_path: Path | None
    report_path: Path


def _page_urls(target: Target, offline: bool) -> list[str]:
    if offline or target.max_pages <= 1 or target.page_url_template is None:
        return [target.start_url]
    return [
        target.page_url_template.format(page=page) for page in range(1, target.max_pages + 1)
    ]


def _read_fixture(target: Target, logger: JsonLogger) -> str | None:
    path = FIXTURE_DIR / OFFLINE_FIXTURES[target.name]
    if not path.exists():
        logger.warning("fixture_missing", target=target.name, path=str(path))
        return None
    return path.read_text(encoding="utf-8")


def run_pipeline(
    target_names: list[str],
    settings: Settings | None = None,
    offline: bool = False,
    use_browser: bool = True,
    logger: JsonLogger | None = None,
) -> RunReport:
    """Run the scrape pipeline for the given targets and return a run report."""

    settings = settings or get_settings()
    run_id = new_run_id()
    log = logger or JsonLogger(run_id, log_file=settings.runs_dir / f"{run_id}.log")
    log.info("run_started", targets=target_names, offline=offline)

    fetcher = HttpFetcher(settings)
    browser = BrowserFetcher(settings.user_agents[0])
    metrics = RunMetrics(run_id=run_id, started_at=datetime.now(UTC).isoformat())
    rows: list[dict] = []

    for name in target_names:
        target = TARGETS[name]
        parser = PARSERS[name]
        normalizer = NORMALIZERS[name]

        for url in _page_urls(target, offline):
            html: str | None = None

            if offline:
                html = _read_fixture(target, log)
                if html is None:
                    metrics.pages_failed += 1
                    metrics.record_error(url, "fixture missing")
                    continue
            elif target.needs_browser and use_browser:
                result = browser.render(url, wait_selector=BROWSER_WAIT_SELECTORS.get(name, "body"))
                if result.ok:
                    html = result.html
                else:
                    log.error("browser_fetch_failed", url=url, error=result.error)
            else:
                result = fetcher.fetch(url)
                if result.ok:
                    html = result.text
                else:
                    log.error("http_fetch_failed", url=url, error=result.error)

            metrics.pages_fetched += 1

            if html is None:
                metrics.pages_failed += 1
                metrics.record_error(url, "no content")
                continue

            parsed = parser(html, url)
            normalized = normalizer(parsed, name)
            metrics.items_parsed += len(normalized)
            log.info("page_parsed", target=name, url=url, items=len(normalized))
            rows.extend(normalized)

    unique_rows = deduplicate(rows)

    parquet_path: Path | None = None
    if unique_rows:
        parquet_path = write_parquet(unique_rows, settings.raw_dir / run_id / "items.parquet")

    warehouse = DuckDBWarehouse(settings.warehouse_path)
    try:
        metrics.items_loaded = warehouse.upsert(unique_rows)
        source_counts = {source: warehouse.count(source) for source in target_names}
    finally:
        warehouse.close()

    metrics.finish()
    metrics.proxy_stats = fetcher.proxy_pool.stats()
    report_path = metrics.write(settings.runs_dir)
    log.info(
        "run_finished",
        pages_fetched=metrics.pages_fetched,
        pages_failed=metrics.pages_failed,
        items_parsed=metrics.items_parsed,
        items_loaded=metrics.items_loaded,
    )

    return RunReport(
        run_id=run_id,
        source_counts=source_counts,
        metrics=metrics,
        warehouse_path=settings.warehouse_path,
        parquet_path=parquet_path,
        report_path=report_path,
    )
