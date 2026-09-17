"""Runtime configuration and scrape target definitions."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_USER_AGENTS = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
)


@dataclass(frozen=True)
class Settings:
    """Tunable behaviour for a pipeline run."""

    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("SCRAPER_DATA_DIR", "data")))
    user_agents: tuple[str, ...] = DEFAULT_USER_AGENTS
    contact_email: str = os.environ.get("SCRAPER_CONTACT", "akmalariqs@gmail.com")
    min_delay_seconds: float = float(os.environ.get("SCRAPER_MIN_DELAY", "1.0"))
    max_retries: int = int(os.environ.get("SCRAPER_MAX_RETRIES", "3"))
    backoff_base_seconds: float = 0.5
    timeout_seconds: float = float(os.environ.get("SCRAPER_TIMEOUT", "15"))
    respect_robots: bool = os.environ.get("SCRAPER_RESPECT_ROBOTS", "1") != "0"
    proxy_urls: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            url.strip()
            for url in os.environ.get("SCRAPER_PROXIES", "").split(",")
            if url.strip()
        )
    )
    proxy_max_failures: int = int(os.environ.get("SCRAPER_PROXY_MAX_FAILURES", "3"))
    proxy_cooldown_seconds: float = float(os.environ.get("SCRAPER_PROXY_COOLDOWN", "60"))

    @property
    def warehouse_path(self) -> Path:
        return self.data_dir / "warehouse.duckdb"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"


@dataclass(frozen=True)
class Target:
    """A scrape target: where to fetch, how to parse, and how to paginate."""

    name: str
    entity_type: str
    start_url: str
    needs_browser: bool = False
    max_pages: int = 1
    page_url_template: str | None = None


TARGETS: dict[str, Target] = {
    "books": Target(
        name="books",
        entity_type="product",
        start_url="https://books.toscrape.com/catalogue/page-1.html",
        max_pages=3,
        page_url_template="https://books.toscrape.com/catalogue/page-{page}.html",
    ),
    "quotes": Target(
        name="quotes",
        entity_type="quote",
        start_url="https://quotes.toscrape.com/js/",
        needs_browser=True,
        max_pages=1,
    ),
}

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def get_settings(**overrides: object) -> Settings:
    """Build settings, applying keyword overrides on top of environment defaults."""

    base = Settings()
    if not overrides:
        return base
    return Settings(**{**base.__dict__, **overrides})
