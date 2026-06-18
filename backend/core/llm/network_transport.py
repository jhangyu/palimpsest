"""HTTPX transport that connects only to SSRF-validated provider addresses."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from urllib.parse import urlsplit

import httpx

from .endpoints import normalize_base_url
from .models import ProviderConfig
from .network_policy import (
    NetworkAllowRule,
    NetworkPolicyError,
    Resolver,
    validate_provider_base_url,
)


TransportFactory = Callable[[], httpx.AsyncBaseTransport]


class VerifiedIPTransport(httpx.AsyncBaseTransport):
    """Validate before every request, then connect to the validated IP."""

    def __init__(
        self,
        base_url: str,
        *,
        allow_http_loopback: bool = False,
        allow_rules: Iterable[NetworkAllowRule] = (),
        resolver: Resolver | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        try:
            self._base_url = normalize_base_url(base_url)
        except ValueError:
            raise NetworkPolicyError("invalid provider base URL") from None
        parsed = urlsplit(self._base_url)
        port = parsed.port or (
            443 if parsed.scheme.lower() == "https" else 80
        )
        self._expected_origin = (
            parsed.scheme.lower(),
            (parsed.hostname or "").rstrip(".").lower(),
            port,
        )
        self._allow_http_loopback = allow_http_loopback
        self._allow_rules = tuple(allow_rules)
        self._resolver = resolver
        self._transport = transport or httpx.AsyncHTTPTransport(
            retries=0,
            trust_env=False,
        )

    async def handle_async_request(
        self,
        request: httpx.Request,
    ) -> httpx.Response:
        request_origin = (
            request.url.scheme.lower(),
            request.url.host.rstrip(".").lower(),
            request.url.port
            or (443 if request.url.scheme.lower() == "https" else 80),
        )
        if request_origin != self._expected_origin:
            raise NetworkPolicyError(
                "provider request origin does not match configured base URL"
            )

        destination = await validate_provider_base_url(
            self._base_url,
            allow_http_loopback=self._allow_http_loopback,
            allow_rules=self._allow_rules,
            resolver=self._resolver,
        )
        pinned_ip = destination.resolved_ips[0]
        headers = httpx.Headers(request.headers)
        headers["host"] = destination.host_header
        extensions = dict(request.extensions)
        extensions["sni_hostname"] = destination.server_hostname
        pinned_request = httpx.Request(
            method=request.method,
            url=request.url.copy_with(host=pinned_ip),
            headers=headers,
            content=request.stream,
            extensions=extensions,
        )
        return await self._transport.handle_async_request(pinned_request)

    async def aclose(self) -> None:
        await self._transport.aclose()


def create_secure_client_factory(
    *,
    allow_http_loopback: bool = False,
    allow_rules: Iterable[NetworkAllowRule] = (),
    resolver: Resolver | None = None,
    transport_factory: TransportFactory | None = None,
) -> Callable[[ProviderConfig], httpx.AsyncClient]:
    """Return a factory compatible with BaseHTTPProvider.client_factory."""

    rules = tuple(allow_rules)

    def factory(config: ProviderConfig) -> httpx.AsyncClient:
        inner_transport = (
            transport_factory()
            if transport_factory is not None
            else httpx.AsyncHTTPTransport(retries=0, trust_env=False)
        )
        return httpx.AsyncClient(
            transport=VerifiedIPTransport(
                config.base_url,
                allow_http_loopback=allow_http_loopback,
                allow_rules=rules,
                resolver=resolver,
                transport=inner_transport,
            ),
            timeout=httpx.Timeout(config.timeout_seconds),
            follow_redirects=False,
            trust_env=False,
        )

    return factory
