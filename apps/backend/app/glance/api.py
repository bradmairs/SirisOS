"""A glance for an iPhone Home Screen widget (9.3). A web app can't make a widget, but Scriptable (or Shortcuts) can
draw one from a small feed. The feed is read-only and opens with its own key, not your sign-in: make one in Settings,
paste it into the widget script, and make a new one (which stops the old) if a phone is lost.

    GET    /api/v1/glance?key=     the next event, tasks today, readiness, the next workout, habits, a rest running,
                                   a renewal due within 30 days
    GET    /api/v1/glance/key      whether a key is set (signed in)
    POST   /api/v1/glance/key      a new key, shown once (signed in)
    DELETE /api/v1/glance/key      stop the widget (signed in)
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import require_user
from app.hub.service import Hub, get_hub
from app.services import json_store

router = APIRouter(prefix="/api/v1/glance", tags=["glance"])


def _path():
    return json_store.data_path("SIRISOS_GLANCE_PATH", "glance.json")


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _stored() -> dict[str, Any]:
    return json_store.read(_path(), {})


@router.get("/key", dependencies=[Depends(require_user)])
def key_status() -> dict[str, Any]:
    s = _stored()
    return {"set": bool(s.get("hash")), "created": s.get("created")}


@router.post("/key", dependencies=[Depends(require_user)])
def new_key() -> dict[str, Any]:
    key = "glance_" + secrets.token_urlsafe(24)
    json_store.write(_path(), {"hash": _hash(key), "created": datetime.now().isoformat(timespec="seconds")})
    return {"key": key}


@router.delete("/key", dependencies=[Depends(require_user)])
def drop_key() -> dict[str, Any]:
    json_store.write(_path(), {})
    return {"set": False}


async def _quiet(coro, seconds: float = 5.0):
    try:
        return await asyncio.wait_for(coro, seconds)
    except Exception:  # noqa: BLE001 - a widget shows what it can
        return None


def _safe(fn):
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return None


@router.get("")
async def glance(key: str = Query(default="", max_length=100), hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    stored = _stored().get("hash")
    if not stored or not key or not hmac.compare_digest(stored, _hash(key)):
        raise HTTPException(status_code=401, detail="Make a widget key in SirisOS Settings.")
    from app.brief.service import zone

    now = datetime.now(zone())
    today = now.date()
    out: dict[str, Any] = {"at": now.isoformat(timespec="minutes")}

    async def tasks_part():
        from app.tasks import service as tasks

        listing = await tasks.collect(hub, today)
        due = listing["groups"]["overdue"] + listing["groups"]["today"]
        return {"count": len(due), "next": (due[0].get("title") if due else None)}

    async def event_part():
        from app.calendar import service as calendar

        cal = await calendar.events(hub, today, today + timedelta(days=1))
        upcoming = sorted((e for e in cal.get("events") or [] if len(str(e.get("start", ""))) > 10 and str(e["start"]) >= now.isoformat()[:16]),
                          key=lambda e: str(e["start"]))
        return {"title": upcoming[0].get("summary"), "start": upcoming[0]["start"]} if upcoming else None

    async def readiness_part():
        from app.health import service as health

        r = await health.readiness(hub)
        return {"score": r.get("score"), "band": r.get("band")} if r else None

    tasks_now, event, ready = await asyncio.gather(_quiet(tasks_part()), _quiet(event_part()), _quiet(readiness_part()))
    out.update(tasks=tasks_now, event=event, readiness=ready)

    def gym_part():
        from app.gym import service as gym, store as gym_store

        doc = gym_store.load()
        active = next((r for r in doc.routines if r.active), None)
        if not active or not active.days:
            return None
        day = active.days[gym.next_day(doc, active.id, today) % len(active.days)]
        return {"next": day.name, "trained_today": any(gym.day_of(s.started_at) == today.isoformat() for s in doc.sessions)}

    def rest_part():
        from app.gym import api as gym_api

        until = gym_api.rest_info.get("until")
        return {"until": datetime.fromtimestamp(until, zone()).isoformat(timespec="seconds"), "next": gym_api.rest_info.get("next")} if until and until > time.time() else None

    def habits_part():
        from app.mind import service as mind

        hs = mind.habits(today)
        return {"done": sum(1 for h in hs if h["today"]), "of": len(hs), "left": [h["name"] for h in hs if not h["today"]][:3]} if hs else None

    def renewal_part():
        from app.renewals import service as renewals

        soon = [r for r in renewals.listing(today) if r["days_left"] <= 30]
        return {"name": soon[0]["name"], "days_left": soon[0]["days_left"]} if soon else None

    out.update(gym=_safe(gym_part), rest=_safe(rest_part), habits=_safe(habits_part), renewal=_safe(renewal_part))
    return out
