"""Mental health (9.1). See service.py.

    GET    /api/v1/mind                  mood and mindful minutes by day (30), this week against last, patterns, journal
    POST   /api/v1/mind/journal          {kind: gratitude|reframe|note, text, extra?}
    DELETE /api/v1/mind/journal/{id}
    POST   /api/v1/mind/sessions         {tool, seconds}: time on a calming tool (breathing, grounding)
    GET    /api/v1/mind/clarity          the private streak
    POST   /api/v1/mind/clarity/start    {date?}
    POST   /api/v1/mind/clarity/check    {status: clear|slip, note?}
    POST   /api/v1/mind/clarity/urge     {trigger, outcome: rode|slip, note?}
    PUT    /api/v1/mind/clarity/plan     {reasons: [], plan: []}
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_user
from app.hub import sirisai_api
from app.hub.service import Hub, get_hub
from app.mind import service

router = APIRouter(prefix="/api/v1/mind", tags=["mind"], dependencies=[Depends(require_user)])


class JournalIn(BaseModel):
    kind: Literal["gratitude", "reframe", "note"] = "note"
    text: str = Field(min_length=1, max_length=2000)
    extra: dict[str, str] = Field(default_factory=dict, max_length=6)


class SessionIn(BaseModel):
    tool: Literal["breathing", "grounding", "urge"]
    seconds: int = Field(ge=5, le=4 * 3600)


class StartIn(BaseModel):
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class CheckIn(BaseModel):
    status: Literal["clear", "slip"]
    note: str = Field(default="", max_length=300)


class UrgeIn(BaseModel):
    trigger: str = Field(default="", max_length=40)
    outcome: Literal["rode", "slip"] = "rode"
    note: str = Field(default="", max_length=300)


class PlanIn(BaseModel):
    reasons: list[str] = Field(default_factory=list, max_length=12)
    plan: list[str] = Field(default_factory=list, max_length=12)


@router.get("")
async def overview(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    body = await sirisai_api.get(hub, "/siris/hub/v1/health/days", params={"days": 60}, timeout=8.0)
    days = None if body is None or body.get("guest_mode") else list(body.get("days") or [])
    return service.overview(days)


@router.post("/journal")
def journal(body: JournalIn) -> dict[str, Any]:
    return service.add_journal(body.kind, body.text, {k[:20]: v[:500] for k, v in body.extra.items()})


@router.delete("/journal/{entry_id}")
def delete_journal(entry_id: str) -> dict[str, Any]:
    if not service.delete_journal(entry_id):
        raise HTTPException(status_code=404, detail="No such entry.")
    return {"deleted": entry_id}


@router.post("/sessions")
def session(body: SessionIn) -> dict[str, Any]:
    return service.add_session(body.tool, body.seconds)


@router.get("/clarity")
def clarity() -> dict[str, Any]:
    return service.clarity()


@router.post("/clarity/start")
def start(body: StartIn) -> dict[str, Any]:
    return service.start(body.date)


@router.post("/clarity/check")
def check(body: CheckIn) -> dict[str, Any]:
    return service.check(body.status, body.note)


@router.post("/clarity/urge")
def urge(body: UrgeIn) -> dict[str, Any]:
    return service.urge(body.trigger.strip(), body.outcome, body.note)


@router.put("/clarity/plan")
def plan(body: PlanIn) -> dict[str, Any]:
    return service.set_plan(body.reasons, body.plan)
