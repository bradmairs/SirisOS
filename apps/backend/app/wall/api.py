"""The wall display (11.15): a spare tablet in the kitchen, always on, showing the day at a glance.

The tablet never signs in. The wall's page opens with its own key (made on SirisOS's Settings → Wall display, shown
once), which can only read this one feed: the time of day, today's weather, today's and tomorrow's events (titles and
times), bin night, tonight's dinner and parcels on the way. Nothing else in SirisOS opens with it, so a tablet
left on the bench can't show your tasks, health, money or notes. A new key stops the old one.

    GET    /api/v1/wall?key=      the feed (no sign-in)
    GET    /api/v1/wall/key       signed in: whether there's a key
    POST   /api/v1/wall/key       signed in: a new key, shown once (with the page's address)
    DELETE /api/v1/wall/key       signed in: turn the wall off

`dim` is true from wind-down to the morning (Times of day), when the page dims.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import secrets
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import require_user
from app.brief.service import zone
from app.hub import sirisai_api
from app.hub.service import Hub, get_hub
from app.services import json_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/wall", tags=["wall"])
DIM_PHASES = ("winddown", "night")


def _path():
    return json_store.data_path("SIRISOS_WALL_PATH", "wall.json")


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


@router.get("/key", dependencies=[Depends(require_user)])
def key_status() -> dict[str, Any]:
    stored = json_store.read(_path(), {})
    return {"on": bool(stored.get("hash")), "made": stored.get("created")}


@router.post("/key", dependencies=[Depends(require_user)])
def new_key() -> dict[str, Any]:
    key = "wall_" + secrets.token_urlsafe(24)
    json_store.write(_path(), {"hash": _hash(key), "created": datetime.now(zone()).isoformat(timespec="seconds")})
    return {"key": key, "path": f"/wall?key={key}"}


@router.delete("/key", dependencies=[Depends(require_user)])
def drop_key() -> dict[str, Any]:
    json_store.write(_path(), {})
    return {"on": False}


async def _part(coro: Any, seconds: float = 8.0) -> Any:
    try:
        return await asyncio.wait_for(coro, seconds)
    except Exception:  # noqa: BLE001 - one source down never blanks the wall
        logger.info("A wall source didn't answer", exc_info=True)
        return None


def _event(e: dict[str, Any]) -> dict[str, Any]:
    return {"title": e.get("title") or "Event", "start": e.get("start"), "end": e.get("end"), "all_day": bool(e.get("all_day"))}


async def _dinner() -> dict[str, Any] | None:
    from app.meals import api as meals

    got = await meals.get_tonight()
    d = (got or {}).get("dinner")
    return {"title": d.get("title")} if isinstance(d, dict) and d.get("title") else None


@router.get("")
async def wall(key: str = Query(default="", max_length=100), hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    stored = json_store.read(_path(), {}).get("hash") or ""
    if not stored or not key or not hmac.compare_digest(stored, _hash(key)):
        raise HTTPException(status_code=401, detail="This wall's key isn't right: make a new one on SirisOS's Settings → Wall display.")
    from app.home import context
    from app.household import bins

    now = datetime.now(zone())
    ctx, widgets, dinner = await asyncio.gather(_part(context.current(hub, now)), _part(sirisai_api.get(hub, "/siris/hub/v1/widgets", timeout=6.0)),
                                                _part(_dinner()))
    ctx = ctx or {}
    try:
        bin_card = bins.card(now)
    except Exception:  # noqa: BLE001
        bin_card = None
    today = now.date().isoformat()
    events = [_event(e) for e in ctx.get("events") or []]
    parcels = [{"name": p.get("name") or p.get("title") or "Parcel", "status": p.get("status") or p.get("state") or "", "eta": p.get("eta") or p.get("expected")}
               for p in ((widgets or {}).get("parcels") or [])][:4]
    phase = ctx.get("phase") or context.phase(now)
    return {
        "now": now.isoformat(timespec="minutes"), "phase": phase, "dim": phase in DIM_PHASES,
        "weather": ctx.get("weather_today"), "weather_tomorrow": ctx.get("weather_tomorrow"),
        "today": [e for e in events if str(e["start"])[:10] == today][:6],
        "tomorrow": [e for e in events if str(e["start"])[:10] > today][:4],
        "bins": bin_card, "dinner": dinner, "parcels": parcels,
    }
