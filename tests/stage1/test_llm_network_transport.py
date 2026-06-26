"""
---
name: test_llm_network_transport
description: "Tests for verified-IP HTTP transport ensuring DNS pinning and SSRF protection"
stage: stage1
type: pytest
target:
  layer: backend
  domain: llm-network-transport
spec_doc: null
test_file: tests/stage1/test_llm_network_transport.py
functions:
  - name: test_transport_pins_ip_and_preserves_host_and_sni
    line: 93
    purpose: "Verifies VerifiedIPTransport rewrites request URL to pinned IP while keeping Host header and SNI"
    fixtures: []
  - name: test_factory_matches_a1_client_factory_contract
    line: 115
    purpose: "Verifies create_secure_client_factory returns a compliant async context manager client factory"
    fixtures: []
  - name: test_redirect_is_returned_without_following
    line: 137
    purpose: "Verifies 3xx responses are returned as-is without redirect following"
    fixtures: []
  - name: test_transport_rejects_private_and_mixed_dns
    line: 161
    purpose: "Verifies VerifiedIPTransport raises NetworkPolicyError for private or mixed public/private DNS answers"
    fixtures: [addresses]
  - name: test_transport_revalidates_before_each_request
    line: 178
    purpose: "Verifies DNS policy is re-evaluated on each request; second request fails if IP changes to private"
    fixtures: []
  - name: test_transport_rejects_request_for_other_origin
    line: 204
    purpose: "Verifies VerifiedIPTransport raises NetworkPolicyError if request URL does not match the pinned origin"
    fixtures: []
  - name: test_transport_fails_closed_for_unsafe_configured_base_url
    line: 226
    purpose: "Verifies VerifiedIPTransport raises NetworkPolicyError at construction time for unsafe base URLs"
    fixtures: [base_url]
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_llm_network_transport.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---
"""

from __future__ import annotations

import httpx
import pytest

from backend.core.llm.models import ProviderConfig
from backend.core.llm.network_policy import NetworkPolicyError
from backend.core.llm.network_transport import (
    VerifiedIPTransport,
    create_secure_client_factory,
)


def resolver(*addresses: str):
    async def resolve(hostname: str, port: int):
        return addresses

    return resolve


class RecordingTransport(httpx.AsyncBaseTransport):
    def __init__(self, status_code: int = 200) -> None:
        self.requests: list[httpx.Request] = []
        self.status_code = status_code
        self.closed = False

    async def handle_async_request(
        self,
        request: httpx.Request,
    ) -> httpx.Response:
        self.requests.append(request)
        headers = (
            {"location": "https://other.example/redirected"}
            if 300 <= self.status_code < 400
            else {}
        )
        return httpx.Response(self.status_code, headers=headers)

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_transport_pins_ip_and_preserves_host_and_sni() -> None:
    recording = RecordingTransport()
    transport = VerifiedIPTransport(
        "https://api.example.com:8443/v1",
        resolver=resolver("93.184.216.34"),
        transport=recording,
    )
    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.get(
            "https://api.example.com:8443/v1/models"
        )

    assert response.status_code == 200
    assert len(recording.requests) == 1
    request = recording.requests[0]
    assert request.url.host == "93.184.216.34"
    assert request.headers["host"] == "api.example.com:8443"
    assert request.extensions["sni_hostname"] == "api.example.com"
    assert recording.closed is True


@pytest.mark.asyncio
async def test_factory_matches_a1_client_factory_contract() -> None:
    recording = RecordingTransport()
    factory = create_secure_client_factory(
        resolver=resolver("93.184.216.34"),
        transport_factory=lambda: recording,
    )

    async with factory(
        ProviderConfig(
            base_url="https://api.example.com",
            timeout_seconds=3,
        )
    ) as client:
        await client.post("https://api.example.com/v1/messages")

    assert recording.requests[0].url.host == "93.184.216.34"
    assert recording.requests[0].extensions["sni_hostname"] == (
        "api.example.com"
    )


@pytest.mark.asyncio
async def test_redirect_is_returned_without_following() -> None:
    recording = RecordingTransport(status_code=302)
    factory = create_secure_client_factory(
        resolver=resolver("93.184.216.34"),
        transport_factory=lambda: recording,
    )

    async with factory(
        ProviderConfig(base_url="https://api.example.com")
    ) as client:
        response = await client.get("https://api.example.com/v1/models")

    assert response.status_code == 302
    assert len(recording.requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "addresses",
    [
        ("10.0.0.5",),
        ("93.184.216.34", "10.0.0.5"),
    ],
)
async def test_transport_rejects_private_and_mixed_dns(
    addresses: tuple[str, ...],
) -> None:
    recording = RecordingTransport()
    transport = VerifiedIPTransport(
        "https://api.example.com",
        resolver=resolver(*addresses),
        transport=recording,
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(NetworkPolicyError):
            await client.get("https://api.example.com/v1/models")

    assert recording.requests == []


@pytest.mark.asyncio
async def test_transport_revalidates_before_each_request() -> None:
    calls = 0

    async def changing_resolver(hostname: str, port: int):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ("93.184.216.34",)
        return ("10.0.0.5",)

    recording = RecordingTransport()
    transport = VerifiedIPTransport(
        "https://api.example.com",
        resolver=changing_resolver,
        transport=recording,
    )
    async with httpx.AsyncClient(transport=transport) as client:
        await client.get("https://api.example.com/v1/models")
        with pytest.raises(NetworkPolicyError):
            await client.get("https://api.example.com/v1/models")

    assert calls == 2
    assert len(recording.requests) == 1


@pytest.mark.asyncio
async def test_transport_rejects_request_for_other_origin() -> None:
    recording = RecordingTransport()
    transport = VerifiedIPTransport(
        "https://api.example.com",
        resolver=resolver("93.184.216.34"),
        transport=recording,
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(NetworkPolicyError):
            await client.get("https://other.example/v1/models")

    assert recording.requests == []


@pytest.mark.parametrize(
    "base_url",
    [
        "https://user:pass@api.example.com",
        "https://api.example.com?key=secret",
        "https://api.example.com#fragment",
    ],
)
def test_transport_fails_closed_for_unsafe_configured_base_url(
    base_url: str,
) -> None:
    with pytest.raises(NetworkPolicyError):
        VerifiedIPTransport(base_url)
