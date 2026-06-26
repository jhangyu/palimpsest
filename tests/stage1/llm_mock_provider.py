"""
---
name: llm-mock-provider
description: "Shared mock HTTP server for LLM adapter tests"
type: mock
target:
  layer: backend
  domain: llm
run:
  command: "PYTHONPATH=.:backend:tests python -m pytest tests/test_llm_baseline_contract.py -v --co"
  env: {}
  prerequisites:
    - "Python deps installed"
    - "Fixture data at tests/fixtures/ai_provider/"
expected:
  pass: 0
  output: "Mock server fixture import"
---

Deterministic HTTP mock shared by future LLM adapter contract tests.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.parse import urlsplit


FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "ai_provider" / "protocol_responses.json"
)


@dataclass(frozen=True)
class RecordedRequest:
    method: str
    path: str
    query: str
    headers: dict[str, str]
    json_body: Any


class MockProviderServer(AbstractContextManager["MockProviderServer"]):
    """Serve OpenAI, Anthropic, and Gemini-compatible fixture responses."""

    def __init__(self) -> None:
        self.requests: list[RecordedRequest] = []
        self._fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._thread = Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def __enter__(self) -> "MockProviderServer":
        self._thread.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self._dispatch()

            def do_POST(self) -> None:
                self._dispatch()

            def log_message(self, format: str, *args: object) -> None:
                return

            def _dispatch(self) -> None:
                parsed = urlsplit(self.path)
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                json_body = json.loads(body) if body else None
                owner.requests.append(
                    RecordedRequest(
                        method=self.command,
                        path=parsed.path,
                        query=parsed.query,
                        headers={key.lower(): value for key, value in self.headers.items()},
                        json_body=json_body,
                    )
                )

                fixture = owner._response_for(self.command, parsed.path)
                if fixture is None:
                    self._send_json(404, {"error": {"message": "mock route not found"}})
                    return
                self._send_json(200, fixture)

            def _send_json(self, status: int, payload: Any) -> None:
                encoded = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        return Handler

    def _response_for(self, method: str, path: str) -> Any | None:
        if method == "GET" and path == "/v1/models":
            return self._fixtures["openai"]["models"]
        if method == "POST" and path == "/v1/chat/completions":
            return self._fixtures["openai"]["generation"]
        if method == "GET" and path == "/anthropic/v1/models":
            return self._fixtures["anthropic"]["models"]
        if method == "POST" and path == "/anthropic/v1/messages":
            return self._fixtures["anthropic"]["generation"]
        if method == "GET" and path == "/v1beta/models":
            return self._fixtures["gemini"]["models"]
        if (
            method == "POST"
            and path.startswith("/v1beta/models/")
            and path.endswith(":generateContent")
        ):
            return self._fixtures["gemini"]["generation"]
        return None
