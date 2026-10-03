"""Links API: read and save the launchpad, and check which links are up."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends

from app.auth import require_user
from app.hub import service
from app.links import store

router = APIRouter(prefix="/api/v1/links", tags=["links"], dependencies=[Depends(require_user)])

STATUS_TTL = 60.0
_status_cache: dict[str, tuple[float, dict[str, Any]]] = {}


@router.get("")
async def get_links() -> store.LinksDocument:
    return store.load()


@router.put("")
async def put_links(doc: store.LinksDocument) -> store.LinksDocument:
    return store.save(doc)


async def _probe(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    """Up means the app answered at all (a login page or a 401 still counts),
    like Homarr's ping. Down means no answer: refused, timed out, DNS."""
    cached = _status_cache.get(url)
    if cached and time.monotonic() - cached[0] < STATUS_TTL:
        return cached[1]
    start = time.perf_counter()
    try:
        response = await client.get(url)
        result = {"up": True, "status": response.status_code, "ms": round((time.perf_counter() - start) * 1000)}
    except httpx.HTTPError as exc:
        result = {"up": False, "status": None, "ms": None, "error": type(exc).__name__}
    _status_cache[url] = (time.monotonic(), result)
    return result


@router.get("/status")
async def link_status() -> dict[str, dict[str, Any]]:
    """{link id: {up, status, ms}} for every link. LAN apps often use
    self-signed certificates, so certificates aren't verified here."""
    links = [link for group in store.load().groups for link in group.links]
    async with httpx.AsyncClient(timeout=4.0, verify=False, follow_redirects=False, transport=service.transport) as client:
        results = await asyncio.gather(*(_probe(client, link.url) for link in links))
    return {link.id: result for link, result in zip(links, results)}
