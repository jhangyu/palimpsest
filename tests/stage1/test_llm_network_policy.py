"""
---
name: test_llm_network_policy
description: "Tests for SSRF network policy validation for LLM provider base URLs"
stage: stage1
type: pytest
target:
  layer: backend
  domain: llm-network-policy
spec_doc: null
test_file: tests/stage1/test_llm_network_policy.py
functions:
  - name: test_public_https_destination_is_canonical_and_pinned
    line: 92
    purpose: "Verifies validate_provider_base_url normalizes HTTPS URLs and pins resolved public IPs"
    fixtures: []
  - name: test_non_public_addresses_are_rejected
    line: 116
    purpose: "Verifies that loopback, LAN, link-local, and multicast addresses are rejected"
    fixtures: [address]
  - name: test_mixed_public_private_dns_answers_are_rejected
    line: 125
    purpose: "Verifies that DNS answers mixing public and private IPs are rejected"
    fixtures: []
  - name: test_validation_runs_resolver_for_each_call
    line: 134
    purpose: "Verifies that DNS resolution is performed fresh on every validate_provider_base_url call"
    fixtures: []
  - name: test_exact_allowlist_can_enable_lan_destination
    line: 157
    purpose: "Verifies NetworkAllowRule allows LAN addresses when scheme/host/port/CIDR match exactly"
    fixtures: []
  - name: test_allowlist_requires_exact_scheme_host_port_and_cidr
    line: 175
    purpose: "Verifies allowlist rules are not applied for non-matching hostnames"
    fixtures: []
  - name: test_unsafe_url_forms_are_rejected
    line: 203
    purpose: "Verifies non-https, auth-embedded, query, fragment, and encoded IP URLs are rejected"
    fixtures: [url]
  - name: test_network_policy_uses_strict_shared_base_url_normalizer
    line: 212
    purpose: "Verifies the shared normalizer rejects auth, query, fragment, backslash, encoded, null-byte, and invalid-port URLs"
    fixtures: []
  - name: test_network_policy_traceback_does_not_chain_resolver_secret
    line: 230
    purpose: "Verifies resolver exceptions are not chained so secrets in OSError are not leaked in traceback"
    fixtures: []
  - name: test_development_loopback_http_requires_explicit_switch
    line: 248
    purpose: "Verifies http://localhost is accepted only when allow_http_loopback=True"
    fixtures: []
  - name: test_development_http_switch_does_not_enable_public_http
    line: 258
    purpose: "Verifies allow_http_loopback=True does not allow plain HTTP to public hosts"
    fixtures: []
  - name: test_redirects_are_disabled
    line: 267
    purpose: "Verifies reject_redirect raises NetworkPolicyError on 3xx and passes on 200"
    fixtures: []
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_llm_network_policy.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---
"""

from __future__ import annotations

import traceback

import pytest

from backend.core.llm.network_policy import (
    NetworkAllowRule,
    NetworkPolicyError,
    reject_redirect,
    validate_provider_base_url,
)


def resolver(*addresses):
    async def resolve(hostname, port):
        return addresses

    return resolve


@pytest.mark.asyncio
async def test_public_https_destination_is_canonical_and_pinned():
    destination = await validate_provider_base_url(
        " HTTPS://API.Example.COM:443/v1/ ",
        resolver=resolver("93.184.216.34"),
    )
    assert destination.canonical_url == "https://api.example.com/v1"
    assert destination.resolved_ips == ("93.184.216.34",)
    assert destination.host_header == "api.example.com"
    assert destination.server_hostname == "api.example.com"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "224.0.0.1",
        "::1",
        "fe80::1",
        "fc00::1",
    ],
)
async def test_non_public_addresses_are_rejected(address):
    with pytest.raises(NetworkPolicyError):
        await validate_provider_base_url(
            "https://provider.example",
            resolver=resolver(address),
        )


@pytest.mark.asyncio
async def test_mixed_public_private_dns_answers_are_rejected():
    with pytest.raises(NetworkPolicyError):
        await validate_provider_base_url(
            "https://provider.example",
            resolver=resolver("93.184.216.34", "10.0.0.5"),
        )


@pytest.mark.asyncio
async def test_validation_runs_resolver_for_each_call():
    calls = 0

    async def changing_resolver(hostname, port):
        nonlocal calls
        calls += 1
        if calls == 1:
            return ("93.184.216.34",)
        return ("10.0.0.5",)

    await validate_provider_base_url(
        "https://provider.example",
        resolver=changing_resolver,
    )
    with pytest.raises(NetworkPolicyError):
        await validate_provider_base_url(
            "https://provider.example",
            resolver=changing_resolver,
        )
    assert calls == 2


@pytest.mark.asyncio
async def test_exact_allowlist_can_enable_lan_destination():
    destination = await validate_provider_base_url(
        "https://llm.internal:8443/api",
        allow_rules=(
            NetworkAllowRule(
                scheme="https",
                hostname="llm.internal",
                port=8443,
                cidrs=("10.20.0.0/16",),
            ),
        ),
        resolver=resolver("10.20.1.5"),
    )
    assert destination.resolved_ips == ("10.20.1.5",)
    assert destination.host_header == "llm.internal:8443"


@pytest.mark.asyncio
async def test_allowlist_requires_exact_scheme_host_port_and_cidr():
    rule = NetworkAllowRule(
        scheme="https",
        hostname="llm.internal",
        port=443,
        cidrs=("10.20.0.0/16",),
    )
    with pytest.raises(NetworkPolicyError):
        await validate_provider_base_url(
            "https://evil-llm.internal",
            allow_rules=(rule,),
            resolver=resolver("10.20.1.5"),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "ftp://provider.example",
        "https://user:pass@provider.example",
        "https://provider.example/#fragment",
        "https://provider.example/?key=secret",
        "https://provider.example\\@127.0.0.1",
        "https://%31%32%37.0.0.1",
        "http://provider.example",
    ],
)
async def test_unsafe_url_forms_are_rejected(url):
    with pytest.raises(NetworkPolicyError):
        await validate_provider_base_url(
            url,
            resolver=resolver("93.184.216.34"),
        )


@pytest.mark.asyncio
async def test_network_policy_uses_strict_shared_base_url_normalizer():
    for url in (
        "https://user:pass@provider.example/v1",
        "https://provider.example/v1?key=secret",
        "https://provider.example/v1#fragment",
        "https://provider.example\\@127.0.0.1",
        "https://%70rovider.example/v1",
        "https://provider.example/\x00secret",
        "https://provider.example:invalid",
    ):
        with pytest.raises(NetworkPolicyError):
            await validate_provider_base_url(
                url,
                resolver=resolver("93.184.216.34"),
            )


@pytest.mark.asyncio
async def test_network_policy_traceback_does_not_chain_resolver_secret():
    secret = "TOP-SECRET-RESOLVER-DETAIL"

    async def failing_resolver(hostname, port):
        raise OSError(secret)

    with pytest.raises(NetworkPolicyError) as captured:
        await validate_provider_base_url(
            "https://provider.example",
            resolver=failing_resolver,
        )

    assert secret not in "".join(
        traceback.format_exception(captured.value)
    )


@pytest.mark.asyncio
async def test_development_loopback_http_requires_explicit_switch():
    destination = await validate_provider_base_url(
        "http://localhost:8080",
        allow_http_loopback=True,
        resolver=resolver("127.0.0.1"),
    )
    assert destination.canonical_url == "http://localhost:8080"


@pytest.mark.asyncio
async def test_development_http_switch_does_not_enable_public_http():
    with pytest.raises(NetworkPolicyError):
        await validate_provider_base_url(
            "http://provider.example",
            allow_http_loopback=True,
            resolver=resolver("93.184.216.34"),
        )


def test_redirects_are_disabled():
    with pytest.raises(NetworkPolicyError):
        reject_redirect(302, "https://other.example")
    reject_redirect(200)
