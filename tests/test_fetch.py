from scraper_pipeline.config import Settings
from scraper_pipeline.fetch import HttpFetcher, RateLimiter


class FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


class FakeSession:
    def __init__(
        self,
        pages: list,
        robots_status: int = 404,
        robots_text: str = "",
    ) -> None:
        self._pages = list(pages)
        self._robots_status = robots_status
        self._robots_text = robots_text
        self.requested_urls: list[str] = []

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        self.requested_urls.append(url)
        if url.endswith("/robots.txt"):
            return FakeResponse(self._robots_status, self._robots_text)
        item = self._pages.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make_settings(**overrides) -> Settings:
    base = {
        "min_delay_seconds": 0.0,
        "respect_robots": False,
        "max_retries": 3,
        "backoff_base_seconds": 0.0,
    }
    base.update(overrides)
    return Settings(**base)


def make_fetcher(settings: Settings, session: FakeSession) -> HttpFetcher:
    return HttpFetcher(settings, session=session, sleep=lambda _seconds: None)


def test_fetch_success():
    session = FakeSession([FakeResponse(200, "<html>ok</html>")])
    result = make_fetcher(make_settings(), session).fetch("https://example.com/a")

    assert result.ok is True
    assert result.text == "<html>ok</html>"
    assert result.attempts == 1


def test_fetch_retries_retryable_status_then_succeeds():
    session = FakeSession([FakeResponse(503), FakeResponse(200, "ok")])
    result = make_fetcher(make_settings(), session).fetch("https://example.com/a")

    assert result.ok is True
    assert result.attempts == 2


def test_fetch_gives_up_after_max_retries():
    session = FakeSession([FakeResponse(500), FakeResponse(500)])
    result = make_fetcher(make_settings(max_retries=2), session).fetch("https://example.com/a")

    assert result.ok is False
    assert result.status == 500
    assert result.attempts == 2


def test_fetch_does_not_retry_non_retryable_status():
    session = FakeSession([FakeResponse(404)])
    result = make_fetcher(make_settings(), session).fetch("https://example.com/missing")

    assert result.ok is False
    assert result.status == 404
    assert len(session.requested_urls) == 1


def test_fetch_retries_on_connection_error():
    import requests

    session = FakeSession([requests.ConnectionError("boom"), FakeResponse(200, "ok")])
    result = make_fetcher(make_settings(), session).fetch("https://example.com/a")

    assert result.ok is True
    assert result.attempts == 2


def test_fetch_respects_robots_disallow():
    session = FakeSession(
        [],
        robots_status=200,
        robots_text="User-agent: *\nDisallow: /private\n",
    )
    result = make_fetcher(make_settings(respect_robots=True), session).fetch(
        "https://example.com/private/page"
    )

    assert result.ok is False
    assert result.error == "blocked by robots.txt"
    assert result.attempts == 0


def test_rate_limiter_sleeps_between_requests():
    slept: list[float] = []
    limiter = RateLimiter(5.0, sleep=slept.append)

    limiter.wait("example.com")
    limiter.wait("example.com")

    assert len(slept) == 1
    assert 0 < slept[0] <= 5.0
