"""HTML parsers for each supported target."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup

RATING_WORDS = {"One", "Two", "Three", "Four", "Five"}
CURRENCY_SYMBOLS = {"£": "GBP", "$": "USD", "€": "EUR"}


@dataclass
class BookRecord:
    """A product scraped from the static books catalogue."""

    title: str
    price: float | None
    currency: str | None
    availability: str
    rating: str
    product_url: str


@dataclass
class QuoteRecord:
    """A quote scraped from the JavaScript-rendered quotes sandbox."""

    text: str
    author: str
    tags: list[str] = field(default_factory=list)
    source_url: str = ""


def _parse_price(raw: str) -> tuple[float | None, str | None]:
    match = re.search(r"([£$€])?\s*([\d.,]+)", raw or "")
    if not match:
        return None, None
    symbol, amount = match.group(1), match.group(2)
    try:
        value = float(amount.replace(",", ""))
    except ValueError:
        return None, None
    return value, CURRENCY_SYMBOLS.get(symbol or "", None)


def _parse_rating(classes: list[str]) -> str:
    for token in classes:
        if token in RATING_WORDS:
            return token
    return "Unknown"


def parse_books_page(html: str, page_url: str) -> list[BookRecord]:
    """Extract product records from a books catalogue listing page."""

    soup = BeautifulSoup(html, "lxml")
    records: list[BookRecord] = []

    for pod in soup.select("article.product_pod"):
        link = pod.select_one("h3 > a")
        if link is None:
            continue
        price_node = pod.select_one("p.price_color")
        availability_node = pod.select_one("p.instock.availability")
        rating_node = pod.select_one("p.star-rating")
        price, currency = _parse_price(price_node.get_text(strip=True) if price_node else "")
        records.append(
            BookRecord(
                title=(link.get("title") or link.get_text(strip=True)).strip(),
                price=price,
                currency=currency,
                availability=(
                    availability_node.get_text(strip=True) if availability_node else "Unknown"
                ),
                rating=_parse_rating(rating_node.get("class", []) if rating_node else []),
                product_url=urljoin(page_url, link.get("href", "")),
            )
        )
    return records


def parse_quotes_page(html: str, page_url: str) -> list[QuoteRecord]:
    """Extract quote records from the JavaScript-rendered quotes page."""

    soup = BeautifulSoup(html, "lxml")
    records: list[QuoteRecord] = []

    for block in soup.select("div.quote"):
        text_node = block.select_one("span.text")
        author_node = block.select_one("small.author")
        if text_node is None or author_node is None:
            continue
        tags = [tag.get_text(strip=True) for tag in block.select("div.tags a.tag")]
        records.append(
            QuoteRecord(
                text=text_node.get_text(strip=True),
                author=author_node.get_text(strip=True),
                tags=tags,
                source_url=page_url,
            )
        )
    return records


PARSERS = {
    "books": parse_books_page,
    "quotes": parse_quotes_page,
}
