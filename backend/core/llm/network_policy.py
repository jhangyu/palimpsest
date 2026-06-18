"""SSRF-safe provider base URL validation and verified destination metadata."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
import ipaddress
import socket
from urllib.parse import urlsplit

from .endpoints import normalize_base_url


class NetworkPolicyError(Exception):
    """Sanitized network-policy failure."""


@dataclass(frozen=True)
class NetworkAllowRule:
    scheme: str
    hostname: str
    port: int
    cidrs: tuple[str, ...]


@dataclass(frozen=True)
class VerifiedDestination:
    canonical_url: str
    scheme: str
    hostname: str
    port: int
    resolved_ips: tuple[str, ...]
    host_header: str
    server_hostname: str


Resolver = Callable[[str, int], Awaitable[Iterable[str]]]


async def validate_provider_base_url(
    base_url: str,
    *,
    allow_http_loopback: bool = False,
    allow_rules: Iterable[NetworkAllowRule] = (),
    resolver: Resolver | None = None,
) -> VerifiedDestination:
    try:
        normalized = normalize_base_url(base_url)
    except ValueError:
        raise NetworkPolicyError("invalid provider base URL") from None
    parsed = urlsplit(normalized)
    scheme = parsed.scheme.lower()
    hostname = parsed.hostname or ""
    port = parsed.port or (443 if scheme == "https" else 80)
    if scheme == "http" and not allow_http_loopback:
        raise NetworkPolicyError("provider base URL must use HTTPS")

    try:
        resolved = tuple(
            dict.fromkeys(
                await (resolver or _resolve_addresses)(hostname, port)
            )
        )
    except NetworkPolicyError:
        raise
    except Exception:
        raise NetworkPolicyError("provider hostname resolution failed") from None
    if not resolved:
        raise NetworkPolicyError("provider hostname did not resolve")

    matching_rule = _matching_rule(scheme, hostname, port, allow_rules)
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for value in resolved:
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            raise NetworkPolicyError("provider hostname resolved to an invalid address") from None
        addresses.append(address)
        if (
            address.is_global
            and not address.is_multicast
            and not address.is_reserved
            and not address.is_unspecified
        ):
            continue
        if (
            scheme == "http"
            and allow_http_loopback
            and address.is_loopback
            and hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            continue
        if matching_rule and _address_allowed(address, matching_rule.cidrs):
            continue
        raise NetworkPolicyError("provider hostname resolved to a non-public address")
    if scheme == "http" and not all(address.is_loopback for address in addresses):
        raise NetworkPolicyError("HTTP is limited to development loopback destinations")

    default_port = 443 if scheme == "https" else 80
    host_header = f"[{hostname}]" if ":" in hostname else hostname
    if port != default_port:
        host_header = f"{host_header}:{port}"
    return VerifiedDestination(
        canonical_url=normalized,
        scheme=scheme,
        hostname=hostname,
        port=port,
        resolved_ips=tuple(str(address) for address in addresses),
        host_header=host_header,
        server_hostname=hostname,
    )


def reject_redirect(status_code: int, location: str | None = None) -> None:
    if 300 <= status_code < 400:
        raise NetworkPolicyError("provider redirects are disabled")


async def _resolve_addresses(hostname: str, port: int) -> tuple[str, ...]:
    try:
        records = await asyncio.to_thread(
            socket.getaddrinfo,
            hostname,
            port,
            type=socket.SOCK_STREAM,
        )
    except OSError:
        raise NetworkPolicyError("provider hostname resolution failed") from None
    return tuple(record[4][0] for record in records)


def _matching_rule(
    scheme: str,
    hostname: str,
    port: int,
    rules: Iterable[NetworkAllowRule],
) -> NetworkAllowRule | None:
    for rule in rules:
        if (
            rule.scheme.lower() == scheme
            and rule.hostname.rstrip(".").lower() == hostname
            and rule.port == port
        ):
            return rule
    return None


def _address_allowed(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
    cidrs: Iterable[str],
) -> bool:
    try:
        return any(address in ipaddress.ip_network(cidr, strict=True) for cidr in cidrs)
    except ValueError:
        raise NetworkPolicyError("network allowlist contains invalid CIDR") from None
