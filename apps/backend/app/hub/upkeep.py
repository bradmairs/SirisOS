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


def _cert(host: str, port: int, timeout: float = 4.0) -> dict[str, Any] | None:
    """The certificate's dates and issuer, read without trusting it (self-signed is fine; we only want the dates)."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=timeout) as raw:
        with context.wrap_socket(raw, server_hostname=host) as tls:
            der = tls.getpeercert(binary_form=True)
    if not der:
        return None
    from cryptography import x509
    from cryptography.x509.oid import NameOID

    c = x509.load_der_x509_certificate(der)
    issuer = ", ".join(a.value for a in c.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)) or c.issuer.rfc4514_string()
    return {"not_before": c.not_valid_before_utc, "not_after": c.not_valid_after_utc, "issuer": str(issuer)}


def judge(not_before: datetime | None, not_after: datetime, now: datetime | None = None) -> dict[str, Any]:
    """When a certificate runs out, and whether that's worth a warning (7.22). A short-lived certificate that renews
    itself (Caddy's own lasts 12 hours and is renewed with a third left) is fine at "0 days": it's judged against its
    own lifetime, so it only warns once under a quarter of that is left, i.e. it stopped renewing."""
    now = now or datetime.now(timezone.utc)
    left = (not_after - now).total_seconds()
    life = (not_after - not_before).total_seconds() if not_before else None
    short = life is not None and life < 7 * 86400
    warning = left < life / 4 if short else left < WARN_DAYS * 86400
    return {"days_left": int(left // 86400) if left >= 0 else -1, "hours_left": round(left / 3600, 1), "lifetime_hours": round(life / 3600, 1) if life else None,
            "short_lived": short, "warning": warning}


async def certificates(urls: list[str]) -> list[dict[str, Any]]:
    targets = sorted({(u.hostname, u.port or 443) for u in map(urlsplit, urls) if u.scheme == "https" and u.hostname})

    async def one(host: str, port: int) -> dict[str, Any]:
        name = f"{host}:{port}" if port != 443 else host
        try:
            got = await asyncio.to_thread(_cert, host, port)
        except (OSError, ssl.SSLError, ValueError) as exc:
            return {"host": name, "expires": None, "days_left": None, "error": type(exc).__name__}
        if not got:
            return {"host": name, "expires": None, "days_left": None}
        return {"host": name, "expires": got["not_after"].isoformat(), "issuer": got["issuer"], **judge(got["not_before"], got["not_after"])}

    return list(await asyncio.gather(*(one(h, p) for h, p in targets[:20])))


async def overview(hub: Hub) -> dict[str, Any]:
    urls = [c.launch_url for c in hub.connectors if c.launch_url]
    sirisai = await sirisai_api.get(hub, "/siris/hub/v1/upkeep", timeout=8.0)
    from app.backup import service as backup

    return {"sirisos": {"version": API_VERSION, "backups": backup.status()}, "sirisai": sirisai, "certificates": await certificates(urls)}
