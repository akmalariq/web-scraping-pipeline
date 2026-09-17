#!/usr/bin/env bash
set -euo pipefail

# Live smoke test: scrape the public sandboxes into a throwaway data directory.
export SCRAPER_DATA_DIR="${SCRAPER_DATA_DIR:-$(mktemp -d)}"
echo "Using data dir: ${SCRAPER_DATA_DIR}"

uv run playwright install chromium
uv run scrape run --site books --max-pages 2
uv run scrape run --site quotes

echo "--- warehouse summary ---"
uv run python -c "
from pathlib import Path
from scraper_pipeline.storage import DuckDBWarehouse

warehouse = DuckDBWarehouse(Path('${SCRAPER_DATA_DIR}') / 'warehouse.duckdb')
for row in warehouse.summary():
    print(row)
warehouse.close()
"
