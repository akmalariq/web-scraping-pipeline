"""Optional headless browser rendering for JavaScript-heavy pages."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RenderResult:
    """Rendered HTML plus basic timing metadata."""

    url: str
    ok: bool
    html: str = ""
    error: str | None = None


class BrowserFetcher:
    """Render pages with Playwright, waiting for a selector before returning HTML.

    Playwright and its browsers are optional. When they are not installed the
    caller receives a clear error rather than an import crash, so the pipeline
    and its tests can run without a headless browser.
    """

    def __init__(self, user_agent: str, timeout_ms: int = 20000, headless: bool = True) -> None:
        self.user_agent = user_agent
        self.timeout_ms = timeout_ms
        self.headless = headless

    def render(self, url: str, wait_selector: str = "body") -> RenderResult:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            return RenderResult(
                url=url,
                ok=False,
                error=f"playwright not installed: {exc}. Run: uv run playwright install chromium",
            )

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=self.headless)
                try:
                    context = browser.new_context(user_agent=self.user_agent)
                    page = context.new_page()
                    page.goto(url, wait_until="networkidle", timeout=self.timeout_ms)
                    page.wait_for_selector(wait_selector, timeout=self.timeout_ms)
                    html = page.content()
                finally:
                    browser.close()
        except Exception as exc:
            return RenderResult(url=url, ok=False, error=f"{type(exc).__name__}: {exc}")

        return RenderResult(url=url, ok=True, html=html)
