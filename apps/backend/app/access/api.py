"""The access check (3.9): is SirisOS working from where you are right now?

Most of it runs on the phone (System status → Check from here), which is
the only place that sees what a network at work, a VPN or a tunnel does.
These give it what only the server knows:

    GET /api/v1/access          where the request came from (home, VPN, the internet),
                                the certificate for the address in use, and whether
                                each terminal host answers from here
    GET /api/v1/access/stream   two events 1.5 s apart: arriving together means
                                something on the way buffers live updates

The WebSocket probe is `/api/v1/terminal/ws?probe=1` (terminal/api.py), so
it goes through the same proxy route the terminal uses.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.auth import require_user
from app.hub import upkeep
from app.terminal import service as terminal

router = APIRouter(prefix="/api/v1/access", tags=["access"], dependencies=[Depends(require_user)])

TAILSCALE = ipaddress.ip_network("100.64.0.0/10")
HOME = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "169.254.0.0/16", "::1/128", "fc00::/7", "fe80::/10")]


def origin_ip(request: Request) -> str:
    """The browser's address: the first X-Forwarded-For hop (Caddy sets it), else the socket's."""
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return forwarded or (request.client.host if request.client else "")


def network_of(ip: str) -> str:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return "unknown"
    if getattr(addr, "ipv4_mapped", None):
        addr = addr.ipv4_mapped
    if addr in TAILSCALE:
        return "vpn"
    if any(addr.version == n.version and addr in n for n in HOME):
        return "home"
    return "internet"


def _reach(host: str, port: int, timeout: float = 3.0) -> int | None:
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return round((time.monotonic() - started) * 1000)
    except OSError:
        return None


@router.get("")
async def check(request: Request) -> dict[str, Any]:
    ip = origin_ip(request)
    host = request.headers.get("host", "")
    hosts = terminal.hosts()
    reach = await asyncio.gather(*(asyncio.to_thread(_reach, h.host, h.port) for h in hosts))
    certs = await upkeep.certificates([f"https://{host}"]) if host and request.headers.get("x-forwarded-proto", request.url.scheme) == "https" else []
    return {
        "client_ip": ip,
        "network": network_of(ip),
        "host": host,
        "certificate": certs[0] if certs else None,
        "terminal": {"enabled": terminal.enabled(),
                     "hosts": [{"name": h.name, "target": h.target, "ms": ms, "reachable": ms is not None} for h, ms in zip(hosts, reach)]},
    }


@router.get("/stream")
async def stream(gap: float = 1.5) -> StreamingResponse:
    gap = max(0.1, min(gap, 5.0))

    async def events() -> AsyncIterator[str]:
        for n in (1, 2):
            yield f"data: {json.dumps({'n': n, 'at': time.time()})}\n\n"
            if n == 1:
                await asyncio.sleep(gap)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
