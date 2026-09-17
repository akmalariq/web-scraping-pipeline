from scraper_pipeline.normalize import COLUMNS, deduplicate, normalize_books, normalize_quotes
from scraper_pipeline.parse import BookRecord, QuoteRecord


def test_normalize_books_matches_common_schema():
    records = [
        BookRecord("A Light in the Attic", 51.77, "GBP", "In stock", "Three", "https://x/1"),
        BookRecord("Tipping the Velvet", 53.74, "GBP", "In stock", "One", "https://x/2"),
    ]
    rows = normalize_books(records, "books", scraped_at="2026-01-01T00:00:00+00:00")

    assert len(rows) == 2
    assert set(rows[0]) == set(COLUMNS)
    assert rows[0]["source"] == "books"
    assert rows[0]["entity_type"] == "product"
    assert rows[0]["price"] == 51.77
    assert rows[0]["scraped_at"] == "2026-01-01T00:00:00+00:00"


def test_normalize_quotes_joins_tags():
    records = [QuoteRecord("Hello", "Someone", ["tag-a", "tag-b"], "https://x/q")]
    rows = normalize_quotes(records, "quotes")

    assert rows[0]["author"] == "Someone"
    assert rows[0]["tags"] == "tag-a,tag-b"
    assert rows[0]["entity_type"] == "quote"


def test_deduplicate_keeps_first_occurrence_per_natural_key():
    records = [
        BookRecord("Same", 1.0, "GBP", "In stock", "Five", "https://x/same"),
        BookRecord("Same", 1.0, "GBP", "In stock", "Five", "https://x/same"),
        BookRecord("Other", 2.0, "GBP", "In stock", "Two", "https://x/other"),
    ]
    rows = deduplicate(normalize_books(records, "books"))

    assert len(rows) == 2
    assert {row["title"] for row in rows} == {"Same", "Other"}
