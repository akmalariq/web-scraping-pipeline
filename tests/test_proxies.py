from scraper_pipeline.proxies import ProxyPool

PROXY_A = "http://proxy-a.local:8080"
PROXY_B = "http://proxy-b.local:8080"
PROXY_C = "http://proxy-c.local:8080"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_pool_disabled_when_no_proxies():
    pool = ProxyPool([])

    assert pool.enabled is False
    assert len(pool) == 0
    assert pool.acquire() is None


def test_acquire_rotates_round_robin():
    pool = ProxyPool([PROXY_A, PROXY_B])

    assert pool.acquire() == PROXY_A
    assert pool.acquire() == PROXY_B
    assert pool.acquire() == PROXY_A


def test_failures_quarantine_a_proxy():
    clock = FakeClock()
    pool = ProxyPool(
        [PROXY_A, PROXY_B], max_consecutive_failures=2, cooldown_seconds=60, clock=clock
    )

    pool.report_failure(PROXY_A)
    pool.report_failure(PROXY_A)

    acquired = {pool.acquire(), pool.acquire(), pool.acquire()}
    assert PROXY_A not in acquired
    assert PROXY_B in acquired

    stats = {entry["proxy"]: entry for entry in pool.stats()}
    assert stats[PROXY_A]["cooling_down"] is True
    assert stats[PROXY_A]["consecutive_failures"] == 2


def test_cooldown_expires_and_proxy_returns():
    clock = FakeClock()
    pool = ProxyPool(
        [PROXY_A, PROXY_B], max_consecutive_failures=1, cooldown_seconds=30, clock=clock
    )

    pool.report_failure(PROXY_A)
    assert pool.acquire() == PROXY_B
    assert pool.acquire() == PROXY_B

    clock.advance(31)
    assert pool.acquire() == PROXY_A


def test_success_resets_consecutive_failures():
    clock = FakeClock()
    pool = ProxyPool(
        [PROXY_A], max_consecutive_failures=2, cooldown_seconds=60, clock=clock
    )

    pool.report_failure(PROXY_A)
    pool.report_success(PROXY_A)
    pool.report_failure(PROXY_A)

    assert pool.acquire() == PROXY_A
    stats = pool.stats()[0]
    assert stats["successes"] == 1
    assert stats["failures"] == 2
    assert stats["cooling_down"] is False


def test_all_proxies_cooling_down_returns_none():
    clock = FakeClock()
    pool = ProxyPool(
        [PROXY_A, PROXY_B], max_consecutive_failures=1, cooldown_seconds=60, clock=clock
    )

    pool.report_failure(PROXY_A)
    pool.report_failure(PROXY_B)

    assert pool.acquire() is None


def test_unknown_proxy_reports_are_ignored():
    pool = ProxyPool([PROXY_A])

    pool.report_success("http://unknown.local:8080")
    pool.report_failure("http://unknown.local:8080")

    assert pool.stats() == [
        {
            "proxy": PROXY_A,
            "successes": 0,
            "failures": 0,
            "consecutive_failures": 0,
            "cooling_down": False,
        }
    ]


def test_stats_are_sorted_by_proxy():
    pool = ProxyPool([PROXY_C, PROXY_A, PROXY_B])

    assert [entry["proxy"] for entry in pool.stats()] == [PROXY_A, PROXY_B, PROXY_C]
