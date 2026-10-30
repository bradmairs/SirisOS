"""Training (5.5) and the Apple Health import. See service.py and health_import.py.

Signed in:
    GET    /api/v1/training                   the race, the plan, this week, today's session, recovery
    PUT    /api/v1/training/race              {name, date, distance_km, goal_time?, start_km?}
    DELETE /api/v1/training/race
    GET    /api/v1/training/feed              the calendar feed's path (with its token)
    POST   /api/v1/training/feed/new          a new token (the old feed stops)
    GET    /api/v1/health/import/status       whether a key is set, and the last import
    POST   /api/v1/health/import/key          a new key, shown once

Public (their own key or token):
    POST   /api/v1/health/import              Apple Health data from the phone -> SirisAI
    GET    /api/v1/training/calendar.ics?t=   the plan as a subscribed calendar
"""

from __future__ import annotations

import hmac
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.auth import require_user
from app.hub import sirisai_api
from app.hub.service import Hub, get_hub
from app.training import health_import, service

router = APIRouter(prefix="/api/v1", tags=["training"], dependencies=[Depends(require_user)])
public_router = APIRouter(prefix="/api/v1", tags=["training"])


@router.get("/training")
async def get_training(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.overview(hub)


@router.put("/training/race")
async def put_race(body: service.Race, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    service.set_race(body)
    return await service.overview(hub)


@router.delete("/training/race")
async def delete_race(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    service.set_race(None)
    return await service.overview(hub)


@router.get("/training/feed")
def feed() -> dict[str, str]:
    return {"path": f"/api/v1/training/calendar.ics?t={service.feed_token()}"}


@router.post("/training/feed/new")
def new_feed() -> dict[str, str]:
    return {"path": f"/api/v1/training/calendar.ics?t={service.new_feed_token()}"}


@router.get("/health/import/status")
def import_status() -> dict[str, Any]:
    return {**health_import.status(), "path": "/api/v1/health/import"}


@router.post("/health/import/key")
def import_key() -> dict[str, Any]:
    return {"key": health_import.new_key(), "path": "/api/v1/health/import"}


@public_router.post("/health/import")
async def health_in(request: Request, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    auth = request.headers.get("authorization", "")
    key = auth[7:] if auth.lower().startswith("bearer ") else request.headers.get("x-health-key")
    if not health_import.check(key):
        raise HTTPException(status_code=401, detail="That isn't SirisOS's health key. Make one on the Training page.")
    raw = await request.body()
    if len(raw) > health_import.MAX_BYTES:
        raise HTTPException(status_code=413, detail="That's more than 10 MB: export fewer days at a time.")
    try:
        body = json.loads(raw or b"{}")
    except ValueError:
        raise HTTPException(status_code=422, detail="Send JSON.") from None
    try:
        result = await sirisai_api.post(hub, "/siris/health/metrics", json=body, timeout=60.0)
    except sirisai_api.SirisAIError as exc:
        health_import.note(None, str(exc))
        raise HTTPException(status_code=exc.status if 400 <= exc.status < 500 else 502, detail=str(exc)) from None
    health_import.note(result)
    return {"ok": True, **{k: v for k, v in (result or {}).items() if k in ("date", "days", "format", "ignored", "stored")}}


@public_router.get("/training/calendar.ics")
async def calendar_feed(t: str = Query(min_length=10, max_length=100), hub: Hub = Depends(get_hub)) -> Response:
    if not hmac.compare_digest(t, service.feed_token()):
        raise HTTPException(status_code=404, detail="No such calendar.")
    days = await service.health_days(hub)
    return Response(service.ics(days=days), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'inline; filename="training.ics"'})
