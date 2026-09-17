"""Command line interface for the scraping pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace

from scraper_pipeline.config import TARGETS, get_settings
from scraper_pipeline.pipeline import run_pipeline


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scrape", description="Run the web scraping and ingestion pipeline."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="scrape targets into the DuckDB warehouse")
    run.add_argument(
        "--site",
        dest="sites",
        action="append",
        choices=sorted(TARGETS),
        help="target(s) to scrape; repeatable (default: all)",
    )
    run.add_argument(
        "--offline",
        action="store_true",
        help="parse bundled fixtures instead of hitting the network",
    )
    run.add_argument(
        "--no-browser",
        action="store_true",
        help="skip headless rendering for JavaScript targets",
    )
    run.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="override the page count for paginated targets",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command != "run":
        return 1

    sites = args.sites or sorted(TARGETS)
    settings = get_settings()

    if args.max_pages:
        for name in sites:
            TARGETS[name] = replace(TARGETS[name], max_pages=args.max_pages)

    report = run_pipeline(
        target_names=sites,
        settings=settings,
        offline=args.offline,
        use_browser=not args.no_browser,
    )

    print(
        json.dumps(
            {
                "run_id": report.run_id,
                "source_counts": report.source_counts,
                "pages_fetched": report.metrics.pages_fetched,
                "pages_failed": report.metrics.pages_failed,
                "items_loaded": report.metrics.items_loaded,
                "warehouse": str(report.warehouse_path),
                "report": str(report.report_path),
            },
            indent=2,
        )
    )
    return 0 if report.metrics.pages_failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
