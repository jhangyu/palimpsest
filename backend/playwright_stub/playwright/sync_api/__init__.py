_STUB_MSG = "playwright stub: install full playwright for browser automation"


class Page:
    """Stub for playwright.sync_api.Page."""


class Response:
    """Stub for playwright.sync_api.Response."""


class Route:
    """Stub for playwright.sync_api.Route."""


class Locator:
    """Stub for playwright.sync_api.Locator."""


class Browser:
    """Stub for playwright.sync_api.Browser."""


class BrowserContext:
    """Stub for playwright.sync_api.BrowserContext."""


class Playwright:
    """Stub for playwright.sync_api.Playwright."""


class TimeoutError(Exception):
    """Stub for playwright.sync_api.TimeoutError."""


def sync_playwright():
    raise RuntimeError(_STUB_MSG)


def expect():
    raise RuntimeError(_STUB_MSG)


__all__ = [
    "Page",
    "Response",
    "Route",
    "Locator",
    "Browser",
    "BrowserContext",
    "Playwright",
    "TimeoutError",
    "sync_playwright",
    "expect",
]
