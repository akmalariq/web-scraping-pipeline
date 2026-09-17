import json

from scraper_pipeline.config import Settings
from scraper_pipeline.pipeline import run_pipeline


def _offline_settings(tmp_path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        min_delay_seconds=0.0,
        respect_robots=False,
        max_retries=1,
    )


def test_offline_pipeline_loads_both_targets(tmp_path):
    report = run_pipeline(
        target_names=["books", "quotes"],
        settings=_offline_settings(tmp_path),
        offline=True,
    )

    assert report.metrics.pages_fetched == 2
    assert report.metrics.pages_failed == 0
    assert report.metrics.items_parsed == 30
    assert report.metrics.items_loaded == 30
    assert report.source_counts == {"books": 20, "quotes": 10}
    assert report.metrics.errors == []


def test_offline_pipeline_writes_artifacts(tmp_path):
    report = run_pipeline(
        target_names=["books"],
        settings=_offline_settings(tmp_path),
        offline=True,
    )

    assert (tmp_path / "warehouse.duckdb").exists()
    assert report.parquet_path is not None and report.parquet_path.exists()
    assert report.report_path.exists()

    payload = json.loads(report.report_path.read_text(encoding="utf-8"))
    assert payload["items_loaded"] == 20
    assert payload["finished_at"] is not None


def test_offline_pipeline_is_idempotent(tmp_path):
    settings = _offline_settings(tmp_path)

    first = run_pipeline(target_names=["books"], settings=settings, offline=True)
    second = run_pipeline(target_names=["books"], settings=settings, offline=True)

    assert first.source_counts["books"] == 20
    assert second.source_counts["books"] == 20
