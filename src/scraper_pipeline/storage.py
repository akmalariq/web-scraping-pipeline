"""Persistence: Parquet files plus a DuckDB warehouse with upserts."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from scraper_pipeline.normalize import COLUMNS

SCHEMA = """
CREATE TABLE IF NOT EXISTS scraped_items (
    source VARCHAR,
    entity_type VARCHAR,
    natural_key VARCHAR PRIMARY KEY,
    title VARCHAR,
    author VARCHAR,
    price DOUBLE,
    currency VARCHAR,
    availability VARCHAR,
    rating VARCHAR,
    tags VARCHAR,
    source_url VARCHAR,
    scraped_at TIMESTAMPTZ
);
"""


def write_parquet(rows: Sequence[dict], path: Path) -> Path:
    """Write normalized rows to a Parquet file and return the path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(list(rows))
    pq.write_table(table, path)
    return path


class DuckDBWarehouse:
    """Thin DuckDB wrapper that loads normalized items idempotently."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._con = duckdb.connect(str(path))
        self._con.execute(SCHEMA)

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        return self._con

    def upsert(self, rows: Sequence[dict]) -> int:
        """Insert rows, replacing any existing row with the same natural key."""

        if not rows:
            return 0
        columns = ", ".join(COLUMNS)
        placeholders = ", ".join(["?"] * len(COLUMNS))
        self._con.execute(
            "CREATE OR REPLACE TEMP TABLE incoming AS "
            f"SELECT {columns} FROM scraped_items WHERE 1=0"
        )
        self._con.executemany(
            f"INSERT INTO incoming ({columns}) VALUES ({placeholders})",
            [[row[column] for column in COLUMNS] for row in rows],
        )
        self._con.execute(
            "DELETE FROM scraped_items USING incoming "
            "WHERE scraped_items.natural_key = incoming.natural_key"
        )
        self._con.execute(
            f"INSERT INTO scraped_items ({columns}) SELECT {columns} FROM incoming"
        )
        return len(rows)

    def count(self, source: str | None = None) -> int:
        if source is None:
            result = self._con.execute("SELECT count(*) FROM scraped_items").fetchone()
        else:
            result = self._con.execute(
                "SELECT count(*) FROM scraped_items WHERE source = ?", [source]
            ).fetchone()
        return int(result[0]) if result else 0

    def summary(self) -> list[tuple[str, str, int]]:
        return self._con.execute(
            "SELECT source, entity_type, count(*) FROM scraped_items "
            "GROUP BY source, entity_type ORDER BY source, entity_type"
        ).fetchall()

    def close(self) -> None:
        self._con.close()
