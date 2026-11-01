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


@router.post("/health/import/test")
async def import_test(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    """Test the sync (6.93): a small Health Auto Export-shaped sample for this hour goes the same way a phone's
    export would, to SirisAI as a dry run (nothing is kept), and comes back with what it read."""
    from datetime import datetime as dt

    from app.tasks.service import zone

    now = dt.now(zone())
    stamp = now.strftime("%Y-%m-%d %H:00:00 %z")
    sample = {"data": {"metrics": [{"name": "step_count", "units": "count", "data": [{"date": stamp, "qty": 1}]}]}}
    status = health_import.status()
    try:
        got = await sirisai_api.post(hub, "/siris/health/metrics?dry_run=1", json=sample, timeout=20.0,
                                     headers={"X-Health-Source": "health_auto_export"}) or {}
    except sirisai_api.SirisAIError as exc:
        return {"ok": False, "step": "SirisAI", "detail": str(exc), "last": status.get("last_ok")}
    if not got:
        return {"ok": False, "step": "SirisAI", "detail": "SirisAI didn't answer: check it's running and SirisOS can reach it.", "last": status.get("last_ok")}
    ok = got.get("dry_run") and (got.get("meta") or {}).get("last_day") == now.date().isoformat()
    return {"ok": bool(ok), "step": "done", "detail": "SirisOS and SirisAI read an export for this hour correctly. If today is still empty, "
            "the phone isn't sending it: check Date Range (Default) and that Health Auto Export can run." if ok else "SirisAI answered but didn't read today.",
            "read": got.get("days"), "last": status.get("last_ok"), "key_set": status.get("has_key")}


@router.post("/health/import/key")
def import_key() -> dict[str, Any]:
    return {"key": health_import.new_key(), "path": "/api/v1/health/import"}


@public_router.post("/health/import")
async def health_in(request: Request, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    """Health Auto Export's JSON goes to SirisAI as it is (5.8): SirisAI 3.51
    reads it and keeps everything (every metric, sleep, workouts) for the
    Health section, chat and voice. Anything else (a Shortcut's simple
    {date, metrics}) is passed on too. Every attempt is logged, with the
    reason when it fails, for the Training page."""
    raw = await request.body()

    def fail(status: int, why: str) -> HTTPException:
        health_import.attempt(status, why, len(raw))
        return HTTPException(status_code=status, detail=why)

    auth = request.headers.get("authorization", "")
    key = auth[7:] if auth.lower().startswith("bearer ") else request.headers.get("x-health-key")
    if not health_import.check(key):
        why = ("No Authorization header: add one with Bearer and your key." if not key
               else "The key doesn't match: copy \"Bearer …\" again from the Training page (a new key stops the old one).")
        raise fail(401, why)
    if len(raw) > health_import.MAX_BYTES:
        raise fail(413, "More than 50 MB: choose fewer metrics, or a shorter date range, or turn on Batch Requests.")
    try:
        body = json.loads(raw or b"{}")
    except ValueError:
        raise fail(422, "That wasn't JSON: set Export Format to JSON.") from None
    exported = isinstance(body, dict) and isinstance(body.get("data"), dict)
    try:
        result = await sirisai_api.post(hub, "/siris/health/metrics", json=body, timeout=180.0,
                                        headers={"X-Health-Source": "health_auto_export" if exported else "shortcut"}) or {}
    except sirisai_api.SirisAIError as exc:
        if exported and exc.status == 422 and "No recognised metrics" in str(exc):
            health_import.note({"format": "health_auto_export", "days": {}})
            health_import.attempt(200, "Nothing SirisAI uses in it (that's fine)", len(raw))
            return {"ok": True, "format": "health_auto_export", "days": {}}
        health_import.note(None, str(exc))
        raise fail(exc.status if 400 <= exc.status < 500 else 502, str(exc)) from None
    health_import.note(result)
    days = sorted(result.get("days") or {}) if isinstance(result.get("days"), dict) else []
    n = len(days) if days else (1 if result.get("date") else 0)
    span = f" ({days[0]} to {days[-1]})" if len(days) > 1 else f" ({days[0]})" if days else ""
    health_import.attempt(200, f"Saved {n} day{'s' if n != 1 else ''}{span}" if n else "Nothing SirisOS uses in it (that's fine)", len(raw))
    return {"ok": True, **{k: v for k, v in result.items() if k in ("date", "days", "format", "ignored", "stored")}}


@public_router.get("/training/calendar.ics")
async def calendar_feed(t: str = Query(min_length=10, max_length=100), hub: Hub = Depends(get_hub)) -> Response:
    if not hmac.compare_digest(t, service.feed_token()):
        raise HTTPException(status_code=404, detail="No such calendar.")
    days = await service.health_days(hub)
    return Response(service.ics(days=days), media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'inline; filename="training.ics"'})
