from scraper_pipeline.config import FIXTURE_DIR
from scraper_pipeline.parse import parse_books_page, parse_quotes_page


def test_parse_books_page_extracts_all_products():
    html = (FIXTURE_DIR / "books_page1.html").read_text(encoding="utf-8")
    records = parse_books_page(html, "https://books.toscrape.com/catalogue/page-1.html")

    assert len(records) == 20
    first = records[0]
    assert first.title
    assert first.price is not None and first.price > 0
    assert first.currency == "GBP"
    assert first.rating in {"One", "Two", "Three", "Four", "Five"}
    assert first.product_url.startswith("https://books.toscrape.com/")


def test_parse_quotes_page_extracts_all_quotes():
    html = (FIXTURE_DIR / "quotes_js_rendered.html").read_text(encoding="utf-8")
    records = parse_quotes_page(html, "https://quotes.toscrape.com/js/")

    assert len(records) == 10
    assert all(record.author for record in records)
    assert all(record.text for record in records)
    assert any(record.tags for record in records)
