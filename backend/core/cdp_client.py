# backend/core/cdp_client.py
"""
---
name: cdp_client
description: "Lightweight async CDP client over WebSocket: replaces Playwright (~136MB) with websockets-based CDP for remote Chrome (browserless) interaction"
type: core
target:
  layer: backend
  domain: crawl
spec_doc: null
test_file: null
functions:
  - name: CDPError
    line: 29
    purpose: "Exception raised when a CDP command returns an error response"
  - name: CDPConnection
    line: 37
    purpose: "Manages WebSocket to Chrome; dispatches messages to browser-level and session-level handlers"
  - name: CDPConnection.send_browser
    line: 71
    purpose: "Send browser-level CDP command (no sessionId); awaitable with timeout"
  - name: CDPConnection.send_session
    line: 87
    purpose: "Send session-level CDP command (with sessionId at top level)"
  - name: _FlatSession
    line: 149
    purpose: "CDP session for a specific target, multiplexed on the browser WebSocket"
  - name: _FlatSession.send
    line: 191
    purpose: "Send CDP command via this session; awaitable with timeout"
  - name: CDPPage
    line: 212
    purpose: "Browser page/tab interface: goto, wait_for_load_state, content(), close()"
  - name: CDPPage.goto
    line: 258
    purpose: "Navigate to URL; timeout in ms; waits for domcontentloaded or networkidle"
  - name: CDPPage.wait_for_selector
    line: 289
    purpose: "Poll DOM until CSS selector matches at least one element"
  - name: CDPPage.content
    line: 307
    purpose: "Return full outer-HTML of the page (mirrors Playwright page.content())"
  - name: CDPContext
    line: 336
    purpose: "Logical BrowserContext: creates pages with shared UA, viewport, headers"
  - name: CDPContext.new_page
    line: 347
    purpose: "Create new tab and apply context-level settings via CDP Emulation/Network domains"
  - name: CDPBrowser
    line: 399
    purpose: "Top-level CDP browser client; connect() → new_context() → new_page() workflow"
  - name: CDPBrowser.connect
    line: 417
    purpose: "Class method: connect to Chrome via CDP WebSocket endpoint"
  - name: CDPBrowser.new_context
    line: 433
    purpose: "Create browser context with given user-agent, viewport, locale, etc."
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""

import asyncio
import json
import logging
from typing import Any

import websockets  # type: ignore[import-untyped]
import websockets.asyncio.client  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NETWORK_IDLE_WAIT_MS = 500  # same as Playwright's networkidle definition


class CDPError(Exception):
    """Raised when a CDP command returns an error."""


# ---------------------------------------------------------------------------
# CDPConnection – low-level WebSocket ↔ CDP message pump
# ---------------------------------------------------------------------------

class CDPConnection:
    """Manages a WebSocket connection to Chrome and dispatches messages to sessions."""

    def __init__(self, ws):
        self._ws = ws
        self._id = 0
        # Browser-level (no sessionId) pending commands
        self._pending: dict[int, asyncio.Future] = {}
        self._event_handlers: dict[str, list] = {}
        # Per-session dispatchers (sessionId -> _FlatSession)
        self._sessions: dict[str, "_FlatSession"] = {}
        self._recv_task: asyncio.Task | None = None

    def start(self):
        self._recv_task = asyncio.ensure_future(self._recv_loop())

    async def close(self):
        if self._recv_task and not self._recv_task.done():
            self._recv_task.cancel()
            try:
                await self._recv_task
            except (asyncio.CancelledError, Exception):
                pass
        try:
            await self._ws.close()
        except Exception:
            pass

    def register_session(self, session_id: str, session: "_FlatSession"):
        self._sessions[session_id] = session

    def unregister_session(self, session_id: str):
        self._sessions.pop(session_id, None)

    async def send_browser(self, method: str, params: dict | None = None, *, timeout: float = 30) -> Any:
        """Send a browser-level CDP command (no sessionId)."""
        self._id += 1
        msg_id = self._id
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = fut
        payload: dict[str, Any] = {"id": msg_id, "method": method}
        if params:
            payload["params"] = params
        await self._ws.send(json.dumps(payload))
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            raise CDPError(f"CDP command {method} timed out after {timeout}s")

    async def send_session(self, session_id: str, msg_id: int, method: str, params: dict | None = None):
        """Send a session-level CDP command (with sessionId at top level)."""
        payload: dict[str, Any] = {
            "id": msg_id,
            "method": method,
            "sessionId": session_id,
        }
        if params:
            payload["params"] = params
        await self._ws.send(json.dumps(payload))

    def on(self, event: str, handler):
        self._event_handlers.setdefault(event, []).append(handler)

    async def _recv_loop(self):
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                session_id = msg.get("sessionId")

                if session_id:
                    # Route to the appropriate flat session
                    session = self._sessions.get(session_id)
                    if session:
                        session._dispatch(msg)
                    continue

                # Browser-level message
                if "id" in msg:
                    fut = self._pending.pop(msg["id"], None)
                    if fut and not fut.done():
                        if "error" in msg:
                            fut.set_exception(CDPError(msg["error"].get("message", str(msg["error"]))))
                        else:
                            fut.set_result(msg.get("result"))
                elif "method" in msg:
                    handlers = self._event_handlers.get(msg["method"], [])
                    for h in handlers:
                        try:
                            h(msg.get("params", {}))
                        except Exception:
                            pass
        except (websockets.ConnectionClosed, asyncio.CancelledError):
            pass
        except Exception as exc:
            logger.debug("CDP recv loop error: %s", exc)
        finally:
            # Resolve all pending futures so callers don't hang
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(CDPError("Connection closed"))
            self._pending.clear()
            # Also clean up sessions
            for session in self._sessions.values():
                session._on_connection_closed()
            self._sessions.clear()


# ---------------------------------------------------------------------------
# _FlatSession – target session multiplexed on the browser WebSocket
# ---------------------------------------------------------------------------

class _FlatSession:
    """CDP session for a specific target within a flattened connection.

    Chrome's flat session mode multiplexes all target sessions onto the single
    browser WebSocket.  Commands carry ``sessionId`` at the top level; events
    arriving with the same ``sessionId`` are routed here by CDPConnection.
    """

    def __init__(self, conn: CDPConnection, session_id: str):
        self._conn = conn
        self._session_id = session_id
        self._id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._event_handlers: dict[str, list] = {}
        conn.register_session(session_id, self)

    def _dispatch(self, msg: dict):
        """Called by CDPConnection when a message arrives for our sessionId."""
        if "id" in msg:
            fut = self._pending.pop(msg["id"], None)
            if fut and not fut.done():
                if "error" in msg:
                    fut.set_exception(CDPError(msg["error"].get("message", str(msg["error"]))))
                else:
                    fut.set_result(msg.get("result"))
        elif "method" in msg:
            handlers = self._event_handlers.get(msg["method"], [])
            for h in handlers:
                try:
                    h(msg.get("params", {}))
                except Exception:
                    pass

    def _on_connection_closed(self):
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(CDPError("Session closed"))
        self._pending.clear()

    def on(self, event: str, handler):
        self._event_handlers.setdefault(event, []).append(handler)

    async def send(self, method: str, params: dict | None = None, *, timeout: float = 30) -> Any:
        self._id += 1
        msg_id = self._id
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = fut
        await self._conn.send_session(self._session_id, msg_id, method, params)
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            raise CDPError(f"CDP command {method} timed out after {timeout}s")

    async def close(self):
        self._conn.unregister_session(self._session_id)
        self._on_connection_closed()


# ---------------------------------------------------------------------------
# CDPPage
# ---------------------------------------------------------------------------

class CDPPage:
    """Represents a single browser page/tab controlled via CDP."""

    def __init__(self, session: _FlatSession, target_id: str, browser: "CDPBrowser"):
        self._session = session
        self._target_id = target_id
        self._browser = browser
        # network-idle tracking
        self._pending_requests: set[str] = set()
        self._network_idle_event: asyncio.Event = asyncio.Event()
        self._lifecycle_events: set[str] = set()
        self._dom_content_loaded: asyncio.Event = asyncio.Event()
        self._setup_listeners()

    def _setup_listeners(self):
        self._session.on("Network.requestWillBeSent", self._on_request_sent)
        self._session.on("Network.loadingFinished", self._on_loading_done)
        self._session.on("Network.loadingFailed", self._on_loading_done)
        self._session.on("Page.lifecycleEvent", self._on_lifecycle)

    def _on_request_sent(self, params: dict):
        req_id = params.get("requestId", "")
        self._pending_requests.add(req_id)
        self._network_idle_event.clear()

    def _on_loading_done(self, params: dict):
        req_id = params.get("requestId", "")
        self._pending_requests.discard(req_id)
        if not self._pending_requests:
            asyncio.ensure_future(self._schedule_idle_check())

    async def _schedule_idle_check(self):
        await asyncio.sleep(_NETWORK_IDLE_WAIT_MS / 1000)
        if not self._pending_requests:
            self._network_idle_event.set()

    def _on_lifecycle(self, params: dict):
        name = params.get("name", "")
        self._lifecycle_events.add(name)
        if name == "DOMContentLoaded":
            self._dom_content_loaded.set()
        if name == "networkIdle":
            self._network_idle_event.set()

    # -- public API (mirrors Playwright Page) --

    async def goto(self, url: str, timeout: int = 60000, wait_until: str = "domcontentloaded"):
        """Navigate to *url*. *timeout* is in milliseconds."""
        self._lifecycle_events.clear()
        self._dom_content_loaded.clear()
        self._network_idle_event.clear()
        self._pending_requests.clear()

        await self._session.send("Page.navigate", {"url": url}, timeout=timeout / 1000)

        if wait_until == "domcontentloaded":
            try:
                await asyncio.wait_for(self._dom_content_loaded.wait(), timeout=timeout / 1000)
            except asyncio.TimeoutError:
                pass  # best-effort, continue
        elif wait_until == "networkidle":
            try:
                await asyncio.wait_for(self._network_idle_event.wait(), timeout=timeout / 1000)
            except asyncio.TimeoutError:
                pass

    async def wait_for_load_state(self, state: str = "networkidle", timeout: int = 15000):
        """Wait for a load state. *timeout* is in milliseconds."""
        if state == "networkidle":
            if self._network_idle_event.is_set():
                return
            await asyncio.wait_for(self._network_idle_event.wait(), timeout=timeout / 1000)
        elif state == "domcontentloaded":
            if self._dom_content_loaded.is_set():
                return
            await asyncio.wait_for(self._dom_content_loaded.wait(), timeout=timeout / 1000)

    async def wait_for_selector(self, selector: str, timeout: int = 10000):
        """Poll DOM until *selector* matches at least one element. *timeout* ms."""
        js = f"document.querySelector({json.dumps(selector)}) !== null"
        deadline = asyncio.get_event_loop().time() + timeout / 1000
        interval = 0.25  # 250ms polling
        while True:
            result = await self._session.send(
                "Runtime.evaluate",
                {"expression": js, "returnByValue": True},
                timeout=5,
            )
            val = result.get("result", {}).get("value", False)
            if val:
                return
            if asyncio.get_event_loop().time() >= deadline:
                raise TimeoutError(f"Selector {selector!r} not found within {timeout}ms")
            await asyncio.sleep(interval)

    async def content(self) -> str:
        """Return the full outer-HTML of the page (like page.content() in Playwright)."""
        result = await self._session.send(
            "Runtime.evaluate",
            {
                "expression": "document.documentElement.outerHTML",
                "returnByValue": True,
            },
            timeout=10,
        )
        return result.get("result", {}).get("value", "")

    async def close(self):
        """Close this page/target."""
        try:
            conn = self._browser._conn
            if conn is not None:
                await conn.send_browser(
                    "Target.closeTarget", {"targetId": self._target_id}, timeout=5
                )
        except Exception:
            pass
        await self._session.close()


# ---------------------------------------------------------------------------
# CDPContext
# ---------------------------------------------------------------------------

class CDPContext:
    """Logical grouping similar to Playwright BrowserContext.

    Creates pages with shared settings (UA, viewport, headers, etc.).
    """

    def __init__(self, browser: "CDPBrowser", **settings):
        self._browser = browser
        self._settings = settings
        self._pages: list[CDPPage] = []

    async def new_page(self) -> CDPPage:
        """Create a new tab and apply context-level settings."""
        page = await self._browser._create_page()
        self._pages.append(page)

        # Apply settings via CDP
        ua = self._settings.get("user_agent")
        locale = self._settings.get("locale")
        timezone_id = self._settings.get("timezone_id")
        viewport = self._settings.get("viewport")
        extra_headers = self._settings.get("extra_http_headers")

        if ua or locale:
            emulation_params: dict[str, Any] = {}
            if ua:
                emulation_params["userAgent"] = ua
            if locale:
                emulation_params["acceptLanguage"] = locale
            await page._session.send("Emulation.setUserAgentOverride", emulation_params)

        if timezone_id:
            try:
                await page._session.send("Emulation.setTimezoneOverride", {"timezoneId": timezone_id})
            except CDPError:
                pass  # older Chrome may not support

        if viewport:
            await page._session.send("Emulation.setDeviceMetricsOverride", {
                "width": viewport.get("width", 1920),
                "height": viewport.get("height", 1080),
                "deviceScaleFactor": 1,
                "mobile": False,
            })

        if extra_headers:
            await page._session.send("Network.setExtraHTTPHeaders", {"headers": extra_headers})

        return page

    async def close(self):
        for page in self._pages:
            try:
                await page.close()
            except Exception:
                pass
        self._pages.clear()


# ---------------------------------------------------------------------------
# CDPBrowser
# ---------------------------------------------------------------------------

class CDPBrowser:
    """Lightweight CDP browser client connected to a remote Chrome instance.

    Usage::

        browser = await CDPBrowser.connect("ws://chrome:3000")
        ctx = await browser.new_context(user_agent="...", viewport={...})
        page = await ctx.new_page()
        await page.goto("https://example.com")
        html = await page.content()
        await browser.close()
    """

    def __init__(self):
        self._conn: CDPConnection | None = None
        self._ws_url: str = ""

    @classmethod
    async def connect(cls, ws_url: str) -> "CDPBrowser":
        """Connect to Chrome via the CDP WebSocket endpoint."""
        browser = cls()
        browser._ws_url = ws_url

        ws = await websockets.asyncio.client.connect(
            ws_url,
            max_size=50 * 1024 * 1024,  # 50MB – pages can be large
            open_timeout=15,
            close_timeout=5,
        )
        conn = CDPConnection(ws)
        conn.start()
        browser._conn = conn
        return browser

    async def new_context(
        self,
        user_agent: str | None = None,
        viewport: dict | None = None,
        locale: str | None = None,
        timezone_id: str | None = None,
        extra_http_headers: dict | None = None,
    ) -> CDPContext:
        """Create a new browser context with the given settings."""
        return CDPContext(
            self,
            user_agent=user_agent,
            viewport=viewport,
            locale=locale,
            timezone_id=timezone_id,
            extra_http_headers=extra_http_headers,
        )

    async def _create_page(self) -> CDPPage:
        """Create a new target (tab) and return a CDPPage connected to it."""
        assert self._conn is not None, "Not connected"

        result = await self._conn.send_browser(
            "Target.createTarget", {"url": "about:blank"}
        )
        target_id = result["targetId"]

        # Attach with flatten=True so session messages are multiplexed on the
        # same WebSocket with a top-level sessionId field.
        attach_result = await self._conn.send_browser(
            "Target.attachToTarget", {"targetId": target_id, "flatten": True}
        )
        session_id = attach_result.get("sessionId", "")

        page_session = _FlatSession(self._conn, session_id)
        page = CDPPage(page_session, target_id, self)

        # Enable domains
        await page_session.send("Page.enable")
        await page_session.send("Page.setLifecycleEventsEnabled", {"enabled": True})
        await page_session.send("Network.enable")

        return page

    async def close(self):
        """Close the browser connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
