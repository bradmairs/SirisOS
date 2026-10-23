"""Upkeep for the System status page (3.6): SirisAI's backups and waiting
update (its /siris/hub/v1/upkeep), SirisOS's own backups (3.7), and when the HTTPS certificates of the
apps' public addresses run out."""

from __future__ import annotations

import asyncio
import socket
import ssl
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from app.hub import sirisai_api
from app.hub.service import Hub
from app.main import API_VERSION

WARN_DAYS = 21


def _expiry(host: str, port: int, timeout: float = 4.0) -> datetime | None:
    """The certificate's notAfter, read without trusting it (self-signed is fine; we only want the date)."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=timeout) as raw:
        with context.wrap_socket(raw, server_hostname=host) as tls:
            der = tls.getpeercert(binary_form=True)
    if not der:
        return None
    from cryptography import x509

    return x509.load_der_x509_certificate(der).not_valid_after_utc


async def certificates(urls: list[str]) -> list[dict[str, Any]]:
    targets = sorted({(u.hostname, u.port or 443) for u in map(urlsplit, urls) if u.scheme == "https" and u.hostname})

    async def one(host: str, port: int) -> dict[str, Any]:
        try:
            end = await asyncio.to_thread(_expiry, host, port)
        except (OSError, ssl.SSLError, ValueError) as exc:
            return {"host": f"{host}:{port}" if port != 443 else host, "expires": None, "days_left": None, "error": type(exc).__name__}
        days = (end - datetime.now(timezone.utc)).days if end else None
        return {"host": f"{host}:{port}" if port != 443 else host, "expires": end.isoformat() if end else None, "days_left": days,
                "warning": days is not None and days < WARN_DAYS}

    return list(await asyncio.gather(*(one(h, p) for h, p in targets[:20])))


async def overview(hub: Hub) -> dict[str, Any]:
    urls = [c.launch_url for c in hub.connectors if c.launch_url]
    sirisai = await sirisai_api.get(hub, "/siris/hub/v1/upkeep", timeout=8.0)
    from app.backup import service as backup

    return {"sirisos": {"version": API_VERSION, "backups": backup.status()}, "sirisai": sirisai, "certificates": await certificates(urls)}
