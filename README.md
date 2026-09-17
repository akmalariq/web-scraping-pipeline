# Web Scraping & Ingestion Pipeline

![CI](https://github.com/akmalariq/web-scraping-pipeline/actions/workflows/ci.yml/badge.svg)

A production-shaped web scraping and ingestion pipeline: polite HTTP fetching with
robots.txt compliance, rate limiting and retries, headless browser rendering for
JavaScript pages, normalization into a shared schema, Parquet output, an idempotent
DuckDB warehouse load, structured logging, run metrics, and Dagster orchestration.

Built to exercise the durable parts of scraping engineering (reliability, orchestration,
observability, idempotency) rather than one-off scripts.

## Architecture

```
targets (config.py)
      │
      ▼
HttpFetcher ── robots.txt check ── rate limiter ── retries + backoff ── UA rotation
      │
      ├── BrowserFetcher (Playwright)  ← for JavaScript-rendered pages
      │
      ▼
parse.py        → typed records (BookRecord, QuoteRecord)
      │
      ▼
normalize.py    → one schema + natural keys + dedupe
      │
      ├── data/raw/<run_id>/items.parquet
      │
      ▼
storage.py      → DuckDB warehouse (idempotent upsert by natural_key)
      │
      ▼
monitoring.py   → JSON logs + data/runs/<run_id>.json metrics
```

## Engineering features

| Area | Implementation |
|---|---|
| Politeness | `robots.txt` enforcement per host, minimum delay per host, `From` header with contact |
| Reliability | Retry on 429/5xx and connection errors, exponential backoff with jitter, timeouts |
| Scale hygiene | Rotating user agents, deduplication by natural key, idempotent warehouse upsert |
| Dynamic pages | Playwright headless rendering with selector waits for JavaScript targets |
| Data contract | One normalized item schema across heterogeneous sources |
| Storage | Parquet per run plus a DuckDB warehouse with a primary key on `natural_key` |
| Orchestration | Dagster asset with a retry policy and a daily schedule (Asia/Jakarta) |
| Observability | Structured JSON logs, per-run metrics (pages, items, failures), run report JSON |
| Quality gates | 30 unit tests on fixtures, ruff lint, GitHub Actions CI with no network needed |

## Data contract

`scraped_items`: `source`, `entity_type`, `natural_key`, `title`, `author`, `price`,
`currency`, `availability`, `rating`, `tags`, `source_url`, `scraped_at`.

## Quickstart

```bash
uv sync --dev

# offline: parse the bundled fixtures (no network), useful for CI and demos
uv run scrape run --offline

# live: scrape the public sandboxes
uv run playwright install chromium
uv run scrape run --site books --max-pages 2
uv run scrape run --site quotes
```

Example output:

```json
{
  "run_id": "20260917T041233-9f3c1a",
  "source_counts": { "books": 20, "quotes": 10 },
  "pages_fetched": 2,
  "pages_failed": 0,
  "items_loaded": 30,
  "warehouse": "data/warehouse.duckdb"
}
```

## Orchestration

```bash
uv sync --extra dagster
uv run dagster dev -f orchestration/dagster_pipeline.py
```

`scraped_items` retries 3 times with a delay and records run metadata (pages, failures,
items loaded) on each materialization. `daily_scrape` runs at 03:00 Asia/Jakarta.

## Tests and CI

```bash
uv run ruff check .
uv run pytest -q
```

CI runs lint and tests on every push and pull request. Tests use HTML fixtures captured
from the sandboxes, so they are deterministic and never hit the network.

## Docker

```bash
docker build -t web-scraping-pipeline .
docker run --rm -v "$PWD/data:/app/data" web-scraping-pipeline run --site books
```

## Scope and ethics

This project deliberately targets **scraping-permitted sandboxes**:
`books.toscrape.com` (static catalogue) and `quotes.toscrape.com` (JavaScript-rendered).
It honours `robots.txt`, throttles per host, identifies itself with a contact header, and
retries politely.

**Out of scope on purpose:** CAPTCHA solving, device-fingerprint spoofing, TLS
interception, and SSL-pinning bypass against third-party apps. Those techniques are used
against systems that have explicitly defended against automation, and building them is
neither appropriate nor what this repository is for.

## Roadmap

- Per-request proxy rotation behind a config flag, with health tracking
- Mobile API inspection lab against an app the author owns, using mitmproxy on a local device
- Prometheus metrics endpoint and alerting on scrape success rate
- Incremental change detection (only write rows whose content hash changed)
