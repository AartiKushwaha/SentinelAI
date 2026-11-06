import asyncio
import hashlib
import ipaddress
import json
import socket
from urllib.parse import urlsplit

from app.targets.base import TargetError


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


async def pin_destination(url: str) -> tuple[str, str, str]:
    """Validate every answer then connect to a numeric address. Keep original TLS identity."""
    try:
        parts = urlsplit(url)
    except ValueError as error:
        raise TargetError("invalid_https_endpoint") from error
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.fragment
        or parts.query
        or "\\" in url
        or "%" in parts.netloc
        or not url.isascii()
        or any(ord(c) <= 32 for c in url)
    ):
        raise TargetError("invalid_https_endpoint")
    try:
        port = parts.port or 443
        answers = await asyncio.get_running_loop().getaddrinfo(
            parts.hostname, port, type=socket.SOCK_STREAM
        )
    except (OSError, ValueError) as exc:
        raise TargetError("resolution_failed") from exc
    if not answers:
        raise TargetError("resolution_failed")
    addresses = [ipaddress.ip_address(str(info[4][0])) for info in answers]
    for ip in addresses:
        if (
            not ip.is_global
            or ip.is_multicast
            or (
                isinstance(ip, ipaddress.IPv6Address)
                and (
                    ip not in ipaddress.ip_network("2000::/3")
                    or ip.ipv4_mapped
                    or ip.sixtofour
                    or ip.teredo
                    or ip in ipaddress.ip_network("64:ff9b::/96")
                )
            )
        ):
            raise TargetError("non_public_destination")
    address = str(addresses[0])
    authority = f"[{address}]" if ":" in address else address
    return f"https://{authority}:{port}{parts.path or '/'}", parts.netloc, parts.hostname
