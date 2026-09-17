"""Dagster orchestration for the scraping pipeline.

Install the optional dependency before running:

    uv sync --extra dagster
    uv run dagster dev -f orchestration/dagster_pipeline.py
"""

from __future__ import annotations

from dagster import (
    Definitions,
    MaterializeResult,
    RetryPolicy,
    ScheduleDefinition,
    asset,
    define_asset_job,
)

from scraper_pipeline.pipeline import run_pipeline

TARGETS = ["books", "quotes"]


@asset(retry_policy=RetryPolicy(max_retries=3, delay=10))
def scraped_items() -> MaterializeResult:
    """Scrape every configured target and load the warehouse."""

    report = run_pipeline(target_names=TARGETS)
    return MaterializeResult(
        metadata={
            "run_id": report.run_id,
            "pages_fetched": report.metrics.pages_fetched,
            "pages_failed": report.metrics.pages_failed,
            "items_loaded": report.metrics.items_loaded,
            "errors": len(report.metrics.errors),
            "warehouse": str(report.warehouse_path),
        }
    )


scrape_job = define_asset_job("scrape_job", selection=[scraped_items])

daily_scrape = ScheduleDefinition(
    job=scrape_job,
    cron_schedule="0 3 * * *",
    execution_timezone="Asia/Jakarta",
)

defs = Definitions(assets=[scraped_items], jobs=[scrape_job], schedules=[daily_scrape])
