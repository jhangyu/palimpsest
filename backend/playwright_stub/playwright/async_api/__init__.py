_STUB_MSG = "playwright stub: install full playwright for browser automation"


class Page:
    """Stub for playwright.async_api.Page."""


class Response:
    """Stub for playwright.async_api.Response."""


class Route:
    """Stub for playwright.async_api.Route."""


class Locator:
    """Stub for playwright.async_api.Locator."""


class Browser:
    """Stub for playwright.async_api.Browser."""


class BrowserContext:
    """Stub for playwright.async_api.BrowserContext."""


class Playwright:
    """Stub for playwright.async_api.Playwright."""


class TimeoutError(Exception):
    """Stub for playwright.async_api.TimeoutError."""


def async_playwright():
    raise RuntimeError(_STUB_MSG)


def expect():
    raise RuntimeError(_STUB_MSG)


# Aliases used by scrapling and our own code
async_Route = Route
AsyncLocator = Locator
async_expect = expect
AsyncPlaywrightTimeoutError = TimeoutError

__all__ = [
    "Page",
    "Response",
    "Route",
    "async_Route",
    "Locator",
    "AsyncLocator",
    "Browser",
    "BrowserContext",
    "Playwright",
    "TimeoutError",
    "AsyncPlaywrightTimeoutError",
    "async_playwright",
    "expect",
    "async_expect",
]
