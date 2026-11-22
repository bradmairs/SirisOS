"""11.3: SirisOS doing more of the thinking.

    POST /api/v1/capture/route     {text}: file one line where it belongs (or {handled: false}: a note for Siris)
    POST /api/v1/capture/undo      {undo}: take back what route did
    GET  /api/v1/plan/today        today's tasks fitted into the calendar's free time
    GET  /api/v1/home/usage        what Home has learned about the cards you use, by part of the day
    POST /api/v1/home/usage        {events: [{phase, widget, kind: seen|tap, interactive?}]}
    PUT  /api/v1/home/usage        {on}: learn from what I use, or not
    GET  /api/v1/patterns          patterns across sections (?fresh=1 to work them out again now)
    GET  /api/v1/goals/steer       each yearly goal's pace, projected finish and, if it's behind, a step this week
    GET  /api/v1/away              after 20 hours away, what changed and what's waiting ({away: false} otherwise)
    POST /api/v1/away/done         {keys}: got it (marks them seen)
    GET  /api/v1/facts?topic=      SirisOS's own data for SirisAI: spending, budget, subscriptions, meals, goals, plan
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.assist import away, capture, dayplan, facts, goals_steer, homeuse, patterns
from app.auth import require_user
from app.hub.service import Hub, get_hub

router = APIRouter(prefix="/api/v1", tags=["assist"], dependencies=[Depends(require_user)])


def _now() -> datetime:
    from app.brief.service import zone

    return datetime.now(zone())


class CaptureIn(BaseModel):
    text: str = Field(min_length=1, max_length=300)


class UndoIn(BaseModel):
    undo: dict[str, Any]


class UsageEvent(BaseModel):
    phase: str = Field(max_length=20)
    widget: str = Field(min_length=1, max_length=80)
    kind: Literal["seen", "tap"]
    interactive: bool = False


class UsageIn(BaseModel):
    events: list[UsageEvent] = Field(max_length=200)


class OnIn(BaseModel):
    on: bool


class KeysIn(BaseModel):
    keys: list[str] = Field(default_factory=list, max_length=200)


@router.post("/capture/route")
async def route_capture(body: CaptureIn, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await capture.route(hub, body.text, _now())


@router.post("/capture/undo")
async def undo_capture(body: UndoIn) -> dict[str, Any]:
    return {"undone": await capture.undo(body.undo)}


@router.get("/plan/today")
async def plan_today(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await dayplan.today(hub, _now())


@router.get("/home/usage")
def get_usage() -> dict[str, Any]:
    return homeuse.learned(_now().date())


@router.post("/home/usage")
def post_usage(body: UsageIn) -> dict[str, Any]:
    homeuse.record([e.model_dump() for e in body.events], _now().date())
    return {"ok": True}


@router.put("/home/usage")
def put_usage(body: OnIn) -> dict[str, Any]:
    homeuse.set_on(body.on)
    return homeuse.learned(_now().date())


@router.get("/patterns")
async def get_patterns(fresh: bool = False, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    doc = await patterns.current(hub, _now(), fresh=fresh)
    return {k: doc.get(k) for k in ("at", "patterns", "days", "sources")}


@router.get("/goals/steer")
async def steer(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await goals_steer.overview(hub, _now().date())


@router.get("/away")
async def get_away(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await away.summary(hub, _now())


@router.post("/away/done")
def away_done(body: KeysIn) -> dict[str, Any]:
    away.done(body.keys, _now())
    return {"ok": True}


@router.post("/away/touch")
def away_touch() -> dict[str, Any]:
    """The app is open (no summary showing): the clock starts again."""
    away.touch(_now())
    return {"ok": True}


@router.get("/facts")
async def get_facts(topic: str, q: str | None = None, period: str | None = None, start: str | None = None, end: str | None = None,
                    hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    now = _now()
    try:
        return {"topic": topic, **(await facts.answer(hub, topic, now.date(), now, q, period, start, end))}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
