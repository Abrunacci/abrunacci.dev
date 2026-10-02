"""Who is sending: the key the per-address limit counts by.

Caddy connects to this container and passes the visitor's address in ``X-Forwarded-For``. That
header is believed only when the connection really comes from Caddy: any other peer (another
container on the same network) could write whatever it likes in it. Caddy itself has no
``trusted_proxies``, so it replaces whatever header the visitor sent with the address it saw.

IPv4 addresses count one by one. IPv6 addresses count by their /64 block: one subscriber, or one
attacker, usually holds a whole /64 and can switch addresses inside it at will.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import time
from dataclasses import dataclass, field

UNKNOWN = "unknown"
"""When no address can be read. Everyone in that situation shares one key."""

RESOLVE_EVERY_SECONDS = 60.0
"""The proxy's address changes only when its container is recreated."""


def limit_key(address: str) -> str:
    try:
        ip = ipaddress.ip_address(address.strip())
    except ValueError:
        return UNKNOWN
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return str(ip.ipv4_mapped)
        return str(ipaddress.IPv6Network((ip, 64), strict=False))
    return str(ip)


@dataclass
class TrustedProxy:
    """The proxy's addresses, looked up by host name and kept for a minute."""

    host: str
    _addresses: frozenset[str] = field(default=frozenset(), init=False)
    _resolved_at: float = field(default=float("-inf"), init=False)

    async def addresses(self) -> frozenset[str]:
        if not self.host:
            return frozenset()
        now = time.monotonic()
        if now - self._resolved_at >= RESOLVE_EVERY_SECONDS:
            try:
                infos = await asyncio.get_running_loop().getaddrinfo(
                    self.host, None, type=socket.SOCK_STREAM
                )
            except OSError:
                # Not found: trust nobody until the next lookup.
                infos = []
            self._addresses = frozenset(_normalize(str(info[4][0])) for info in infos)
            self._resolved_at = now
        return self._addresses


async def visitor_address(peer: str | None, forwarded_for: str | None, proxy: TrustedProxy) -> str:
    """The visitor's address: from the header if the proxy sent it, else the connection's."""
    peer_address = _normalize(peer or "")
    if forwarded_for and peer_address in await proxy.addresses():
        # The last entry is the one the proxy added; anything before it came from the visitor.
        return forwarded_for.rsplit(",", 1)[-1].strip()
    return peer_address


def _normalize(address: str) -> str:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return address
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return str(ip.ipv4_mapped)
    return str(ip)
