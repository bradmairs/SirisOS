"""Inbox API (ADR 110). See service.py for what's in it.

    GET  /api/v1/attention                 the merged inbox
    GET  /api/v1/attention/stream          ...live (Server-Sent Events)
    POST /api/v1/attention/{id}/act        {"action": "approve"} (SirisAI items)
    POST /api/v1/attention/{id}/dismiss    any item
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.attention import service
from app.auth import require_user
from app.hub.service import Hub, get_hub, make_client, shared_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/attention", tags=["attention"], dependencies=[Depends(require_user)])

# How often the stream re-checks SirisOS's own items (apps down, overdue tasks).
OWN_REFRESH_SECONDS = 60.0
KEEPALIVE_SECONDS = 15.0


class ActRequest(BaseModel):
    action: str = Field(min_length=1, max_length=40)


@router.get("")
async def get_inbox(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.inbox(hub)


async def _relay_ai(hub: Hub, item_id: str, action: str) -> dict[str, Any]:
    connector = service.sirisai(hub)
    if connector is None:
        raise HTTPException(status_code=503, detail="SirisAI is not configured.")
    path = f"/siris/hub/v1/attention/{item_id}/" + ("dismiss" if action == "dismiss" else "act")
    try:
        response = await shared_client().post(f"{connector.base_url}{path}", headers=connector.headers(),
                                              json=None if action == "dismiss" else {"action": action}, timeout=60.0)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"SirisAI unreachable: {type(exc).__name__}") from exc
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = response.text[:300]
        raise HTTPException(status_code=response.status_code if response.status_code in (404, 409, 422) else 502, detail=f"SirisAI: {detail}")
    body = response.json()
    return {"item": service.from_ai(body["item"]), "result": body.get("result")}


@router.post("/{item_id}/act")
async def act(item_id: str, request: ActRequest, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    origin, _, rest = item_id.partition(":")
    if origin == "ai" and rest.isdigit():
        return await _relay_ai(hub, rest, request.action)
    if origin == "os" and rest:
        if request.action != "dismiss":
            raise HTTPException(status_code=422, detail="SirisOS's own items can only be dismissed.")
        service.dismiss_local(item_id)
        return {"item": {"id": item_id, "status": "dismissed"}, "result": None}
    raise HTTPException(status_code=404, detail=f"Unknown inbox item: {item_id}")


@router.post("/{item_id}/dismiss")
async def dismiss(item_id: str, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await act(item_id, ActRequest(action="dismiss"), hub)


@router.get("/stream")
async def stream(request: Request, max_events: int = Query(0, ge=0, le=1000), hub: Hub = Depends(get_hub)) -> StreamingResponse:
    """A snapshot of the whole inbox, then every change: SirisAI's feed is
    relayed live (its upserts and removals, ids prefixed), and SirisOS's own
    items are re-checked every minute (a new snapshot when they change). If
    SirisAI's stream drops, the relay reconnects after a pause. `max_events`
    (default 0 = forever) ends the stream after that many events."""
    first = await service.inbox(hub)

    async def events() -> AsyncIterator[str]:
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        ai_open: dict[str, dict[str, Any]] = {i["id"]: i for i in first["items"] if i["origin"] == "sirisai"}
        own: list[dict[str, Any]] = [i for i in first["items"] if i["origin"] == "sirisos"]

        def snapshot(kind: str = "snapshot") -> dict[str, Any]:
            items = service.sort_items(list(ai_open.values()) + own)
            return {"type": kind, "items": items, "counts": service.counts(items)}

        async def relay() -> None:
            while True:
                connector = service.sirisai(hub)
                if connector is None:
                    return
                client = make_client(timeout=httpx.Timeout(10.0, read=None))
                try:
                    async with client.stream("GET", f"{connector.base_url}/siris/hub/v1/attention/stream", headers=connector.headers()) as upstream:
                        if upstream.status_code == 404:
                            return  # an older SirisAI: no feed to relay
                        upstream.raise_for_status()
                        async for line in upstream.aiter_lines():
                            if line.startswith("data: "):
                                await queue.put({"ai": json.loads(line[6:])})
                except (httpx.HTTPError, ValueError) as exc:
                    logger.info("SirisAI attention stream dropped: %s", exc)
                finally:
                    await client.aclose()
                await asyncio.sleep(5)

        async def own_refresh() -> None:
            while True:
                await asyncio.sleep(OWN_REFRESH_SECONDS)
                try:
                    await queue.put({"own": await service.os_items(hub)})
                except Exception as exc:  # noqa: BLE001
                    logger.info("SirisOS inbox refresh failed: %s", exc)

        tasks = [asyncio.create_task(relay()), asyncio.create_task(own_refresh())]
        try:
            yield f"data: {json.dumps(snapshot())}\n\n"
            sent = 1
            upstream_snapshots = 0
            while not await request.is_disconnected() and (not max_events or sent < max_events):
                try:
                    message = await asyncio.wait_for(queue.get(), KEEPALIVE_SECONDS)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if message is None:
                    break
                if "own" in message:
                    if [i["id"] for i in message["own"]] == [i["id"] for i in own]:
                        continue
                    own[:] = message["own"]
                    sent += 1
                    yield f"data: {json.dumps(snapshot())}\n\n"
                    continue
                event = message["ai"]
                items = [service.from_ai(i) for i in event.get("items") or []]
                if event.get("type") == "snapshot":
                    ai_open.clear()
                    ai_open.update({i["id"]: i for i in items})
                    # The first upstream snapshot repeats what `first` already
                    # sent; a later one (after a reconnect) may differ.
                    if upstream_snapshots:
                        sent += 1
                        yield f"data: {json.dumps(snapshot())}\n\n"
                    upstream_snapshots += 1
                    continue
                for item in items:
                    if event.get("type") == "upsert":
                        ai_open[item["id"]] = item
                    else:
                        ai_open.pop(item["id"], None)
                current = snapshot()
                sent += 1
                yield f"data: {json.dumps({'type': event.get('type'), 'items': items, 'counts': current['counts']})}\n\n"
        finally:
            for task in tasks:
                task.cancel()

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
