"""Normalize parsed records into one warehouse-friendly schema."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime

from scraper_pipeline.parse import BookRecord, QuoteRecord

COLUMNS = (
    "source",
    "entity_type",
    "natural_key",
    "title",
    "author",
    "price",
    "currency",
    "availability",
    "rating",
    "tags",
    "source_url",
    "scraped_at",
)


def _natural_key(*parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def _base(
    source: str, entity_type: str, natural_key: str, source_url: str, scraped_at: str
) -> dict:
    return {
        "source": source,
        "entity_type": entity_type,
        "natural_key": natural_key,
        "title": None,
        "author": None,
        "price": None,
        "currency": None,
        "availability": None,
        "rating": None,
        "tags": None,
        "source_url": source_url,
        "scraped_at": scraped_at,
    }


def normalize_books(
    records: Iterable[BookRecord], source: str, scraped_at: str | None = None
) -> list[dict]:
    """Map book records to the common item schema."""

    stamp = scraped_at or datetime.now(UTC).isoformat()
    rows: list[dict] = []
    for record in records:
        row = _base(
            source=source,
            entity_type="product",
            natural_key=_natural_key(source, record.product_url or record.title),
            source_url=record.product_url,
            scraped_at=stamp,
        )
        row.update(
            title=record.title,
            price=record.price,
            currency=record.currency,
            availability=record.availability,
            rating=record.rating,
        )
        rows.append(row)
    return rows


def normalize_quotes(
    records: Iterable[QuoteRecord], source: str, scraped_at: str | None = None
) -> list[dict]:
    """Map quote records to the common item schema."""

    stamp = scraped_at or datetime.now(UTC).isoformat()
    rows: list[dict] = []
    for record in records:
        row = _base(
            source=source,
            entity_type="quote",
            natural_key=_natural_key(source, record.author, record.text),
            source_url=record.source_url,
            scraped_at=stamp,
        )
        row.update(title=record.text, author=record.author, tags=",".join(record.tags))
        rows.append(row)
    return rows


def deduplicate(rows: Sequence[dict]) -> list[dict]:
    """Keep the first occurrence of each natural key within a run."""

    seen: set[str] = set()
    unique: list[dict] = []
    for row in rows:
        key = row["natural_key"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique
