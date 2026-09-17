"""Proxy rotation with health tracking and automatic quarantine."""

from __future__ import annotations

import itertools
import threading
import time
from dataclasses import dataclass


@dataclass
class ProxyState:
    """Per-proxy counters and cooldown window."""

    url: str
    successes: int = 0
    failures: int = 0
    consecutive_failures: int = 0
    cooldown_until: float = 0.0


class ProxyPool:
    """Rotate proxies and quarantine those that fail repeatedly.

    Proxies are handed out round-robin. A proxy that reaches
    ``max_consecutive_failures`` is put in cooldown and skipped until the
    cooldown expires. When every proxy is cooling down, ``acquire`` returns
    ``None`` so the caller can fall back to a direct connection.
    """

    def __init__(
        self,
        proxies: list[str] | tuple[str, ...] = (),
        max_consecutive_failures: int = 3,
        cooldown_seconds: float = 60.0,
        clock=time.monotonic,
    ) -> None:
        self._lock = threading.Lock()
        self._clock = clock
        self._max_failures = max_consecutive_failures
        self._cooldown = cooldown_seconds
        self._order = [proxy for proxy in proxies if proxy]
        self._states: dict[str, ProxyState] = {url: ProxyState(url) for url in self._order}
        self._cycle = itertools.cycle(self._order) if self._order else None

    @property
    def enabled(self) -> bool:
        return bool(self._order)

    def __len__(self) -> int:
        return len(self._order)

    def acquire(self) -> str | None:
        """Return the next healthy proxy, or None when none is available."""

        if self._cycle is None:
            return None
        with self._lock:
            now = self._clock()
            for _ in range(len(self._order)):
                url = next(self._cycle)
                if self._states[url].cooldown_until <= now:
                    return url
        return None

    def report_success(self, url: str) -> None:
        with self._lock:
            state = self._states.get(url)
            if state is None:
                return
            state.successes += 1
            state.consecutive_failures = 0
            state.cooldown_until = 0.0

    def report_failure(self, url: str) -> None:
        with self._lock:
            state = self._states.get(url)
            if state is None:
                return
            state.failures += 1
            state.consecutive_failures += 1
            if state.consecutive_failures >= self._max_failures:
                state.cooldown_until = self._clock() + self._cooldown

    def stats(self) -> list[dict]:
        now = self._clock()
        with self._lock:
            return [
                {
                    "proxy": url,
                    "successes": state.successes,
                    "failures": state.failures,
                    "consecutive_failures": state.consecutive_failures,
                    "cooling_down": state.cooldown_until > now,
                }
                for url, state in sorted(self._states.items())
            ]
