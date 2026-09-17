"""Polite HTTP fetching: robots.txt compliance, rate limiting, and retries."""

from __future__ import annotations

import itertools
import random
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

from scraper_pipeline.config import Settings

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


@dataclass
class FetchResult:
    """Outcome of a single HTTP fetch."""

    url: str
    ok: bool
    status: int | None = None
    text: str = ""
    attempts: int = 0
    elapsed_seconds: float = 0.0
    error: str | None = None


class RateLimiter:
    """Enforce a minimum interval between requests to the same host."""

    def __init__(self, min_interval_seconds: float, sleep=time.sleep) -> None:
        self._min_interval = max(0.0, min_interval_seconds)
        self._sleep = sleep
        self._lock = threading.Lock()
        self._last_request: dict[str, float] = {}

    def wait(self, host: str) -> float:
        with self._lock:
            now = time.monotonic()
            last = self._last_request.get(host, 0.0)
            delay = max(0.0, self._min_interval - (now - last))
            if delay:
                self._sleep(delay)
            self._last_request[host] = time.monotonic()
        return delay


class RobotsCache:
    """Cache and evaluate robots.txt rules per host."""

    def __init__(self, session: Any, user_agent: str, timeout: float) -> None:
        self._session = session
        self._user_agent = user_agent
        self._timeout = timeout
        self._cache: dict[str, RobotFileParser | None] = {}

    def _parser(self, url: str) -> RobotFileParser | None:
        parsed = urlparse(url)
        host = parsed.netloc
        if host in self._cache:
            return self._cache[host]
        robots_url = urljoin(f"{parsed.scheme}://{host}", "/robots.txt")
        parser: RobotFileParser | None
        try:
            response = self._session.get(robots_url, timeout=self._timeout)
            if response.status_code >= 400:
                parser = None
            else:
                parser = RobotFileParser()
                parser.parse(response.text.splitlines())
        except requests.RequestException:
            parser = None
        self._cache[host] = parser
        return parser

    def allowed(self, url: str) -> bool:
        parser = self._parser(url)
        if parser is None:
            return True
        return parser.can_fetch(self._user_agent, url)


class HttpFetcher:
    """Fetch pages with robots.txt checks, rate limiting, and exponential backoff."""

    def __init__(
        self,
        settings: Settings,
        session: Any | None = None,
        sleep=time.sleep,
    ) -> None:
        self.settings = settings
        self.session = session or requests.Session()
        self._sleep = sleep
        self._limiter = RateLimiter(settings.min_delay_seconds, sleep=sleep)
        self._robots = RobotsCache(self.session, settings.user_agents[0], settings.timeout_seconds)
        self._agents = itertools.cycle(settings.user_agents)

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": next(self._agents),
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "From": self.settings.contact_email,
        }

    def fetch(self, url: str) -> FetchResult:
        start = time.monotonic()
        host = urlparse(url).netloc

        if self.settings.respect_robots and not self._robots.allowed(url):
            return FetchResult(
                url=url,
                ok=False,
                error="blocked by robots.txt",
                elapsed_seconds=time.monotonic() - start,
            )

        last_error: str | None = None
        status: int | None = None

        for attempt in range(1, self.settings.max_retries + 1):
            self._limiter.wait(host)
            try:
                response = self.session.get(
                    url, headers=self._headers(), timeout=self.settings.timeout_seconds
                )
                status = response.status_code
                if status == 200:
                    return FetchResult(
                        url=url,
                        ok=True,
                        status=status,
                        text=response.text,
                        attempts=attempt,
                        elapsed_seconds=time.monotonic() - start,
                    )
                if status not in RETRYABLE_STATUS:
                    return FetchResult(
                        url=url,
                        ok=False,
                        status=status,
                        attempts=attempt,
                        elapsed_seconds=time.monotonic() - start,
                        error=f"unexpected status {status}",
                    )
                last_error = f"retryable status {status}"
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"

            if attempt < self.settings.max_retries:
                self._sleep(self._backoff(attempt))

        return FetchResult(
            url=url,
            ok=False,
            status=status,
            attempts=self.settings.max_retries,
            elapsed_seconds=time.monotonic() - start,
            error=last_error or "fetch failed",
        )

    def _backoff(self, attempt: int) -> float:
        base = self.settings.backoff_base_seconds * (2 ** (attempt - 1))
        return base + random.uniform(0, base / 2)
