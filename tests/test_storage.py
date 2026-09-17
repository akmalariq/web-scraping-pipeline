from scraper_pipeline.normalize import normalize_books
from scraper_pipeline.parse import BookRecord
from scraper_pipeline.storage import DuckDBWarehouse, write_parquet


def _rows() -> list[dict]:
    records = [
        BookRecord("A Light in the Attic", 51.77, "GBP", "In stock", "Three", "https://x/1"),
        BookRecord("Tipping the Velvet", 53.74, "GBP", "In stock", "One", "https://x/2"),
    ]
    return normalize_books(records, "books", scraped_at="2026-01-01T00:00:00+00:00")


def test_upsert_loads_rows(tmp_path):
    warehouse = DuckDBWarehouse(tmp_path / "warehouse.duckdb")
    try:
        assert warehouse.upsert(_rows()) == 2
        assert warehouse.count("books") == 2
        assert warehouse.summary() == [("books", "product", 2)]
    finally:
        warehouse.close()


def test_upsert_is_idempotent_on_natural_key(tmp_path):
    warehouse = DuckDBWarehouse(tmp_path / "warehouse.duckdb")
    try:
        warehouse.upsert(_rows())
        warehouse.upsert(_rows())
        assert warehouse.count("books") == 2
    finally:
        warehouse.close()


def test_write_parquet_roundtrip(tmp_path):
    path = write_parquet(_rows(), tmp_path / "items.parquet")

    assert path.exists()
    assert path.stat().st_size > 0
