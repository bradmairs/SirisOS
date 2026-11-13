"""Mental health (9.1). See service.py.

    GET    /api/v1/mind                  mood and mindful minutes by day (30), this week against last, patterns, journal
    POST   /api/v1/mind/journal          {kind: gratitude|reframe|note, text, extra?}
    DELETE /api/v1/mind/journal/{id}
    POST   /api/v1/mind/sessions         {tool, seconds}: time on a calming tool (breathing, grounding)
    GET    /api/v1/mind/journal          the journal (unlocked)
    POST   /api/v1/mind/unlock/options; POST /api/v1/mind/unlock   (9.2) Face ID (a passkey) opens the journal and the
                                         private streak for five minutes: X-Mind-Unlock carries the token
    GET    /api/v1/mind/habits; POST /api/v1/mind/habits {name}; POST /api/v1/mind/habits/{id}/check {done, date?};
    PATCH  /api/v1/mind/habits/{id} {name?, archived?}   (9.2) daily habits with streaks
    PUT    /api/v1/mind/clarity/nudge {on}   (9.2)
    GET    /api/v1/mind/clarity          the private streak (unlocked)
    POST   /api/v1/mind/clarity/start    {date?}
    POST   /api/v1/mind/clarity/check    {status: clear|slip, note?}
    POST   /api/v1/mind/clarity/urge     {trigger, outcome: rode|slip, note?}
    PUT    /api/v1/mind/clarity/plan     {reasons: [], plan: []}
"""

from __future__ import annotations

import secrets
import time
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import require_user
from app.hub import sirisai_api
from app.hub.service import Hub, get_hub
from app.mind import service

router = APIRouter(prefix="/api/v1/mind", tags=["mind"], dependencies=[Depends(require_user)])

# -- the lock (9.2) ------------------------------------------------------------------------------------------------
# The journal and the private streak open with Face ID: a passkey assertion, checked here like a sign-in. That gives a
# token good for five minutes from its last use, kept only in memory (a restart locks everything). With no passkey set
# up, there's nothing to check against, so they stay open and the page says how to lock them.
UNLOCK_SECONDS = 300
_unlocked: dict[str, float] = {}


def locking() -> bool:
    from app.security import service as security

    return bool(security.passkeys())


def require_unlocked(x_mind_unlock: str = Header(default="")) -> None:
    if not locking():
        return
    now = time.monotonic()
    for k in [k for k, v in _unlocked.items() if v < now]:
        _unlocked.pop(k, None)
    if not x_mind_unlock or x_mind_unlock not in _unlocked:
        raise HTTPException(status_code=423, detail="Locked. Unlock with Face ID.")
    _unlocked[x_mind_unlock] = now + UNLOCK_SECONDS


class Ceremony(BaseModel):
    challenge: str = Field(min_length=10, max_length=200)
    id: str = Field(default="", max_length=1500)
    response: dict[str, Any]


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
    try:
        from app.gym import service as gym_service, store as gym_store

        trained = {gym_service.day_of(s.started_at) for s in gym_store.load().sessions if any(x.done for e in s.entries for x in e.sets)}
    except Exception:  # noqa: BLE001 - mood works without the gym
        trained = None
    return {**service.overview(days, gym_days=trained), "locking": locking()}


@router.post("/unlock/options")
def unlock_options(request: Request) -> dict[str, Any]:
    from app.security import service as security
    from app.security.api import rp_id_for

    rp_id = rp_id_for(request)
    return {"challenge": security.new_challenge("mind-unlock", rp_id), "rpId": rp_id, "userVerification": "required",
            "allowCredentials": [{"type": "public-key", "id": p.id} for p in security.passkeys() if p.rp_id == rp_id],
            "timeout": security.CHALLENGE_SECONDS * 1000}


@router.post("/unlock")
def unlock(body: Ceremony, request: Request) -> dict[str, Any]:
    from app.security import service as security, webauthn
    from app.security.api import client_of

    client = client_of(request)
    if (wait := security.blocked_for(client)):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again soon.", headers={"Retry-After": str(wait)})
    rp_id = security.take_challenge(body.challenge, "mind-unlock")
    items = security.passkeys()
    found = next((p for p in items if p.id == body.id), None)
    if rp_id is None or found is None or found.rp_id != rp_id:
        security.failed(client)
        raise HTTPException(status_code=401, detail="That passkey isn't set up for SirisOS here.")
    try:
        count = webauthn.verify_assertion(body.response, body.challenge, rp_id, webauthn.unb64url(found.public_key), found.alg, found.sign_count)
    except webauthn.WebAuthnError as exc:
        security.failed(client)
        raise HTTPException(status_code=401, detail=str(exc)) from None
    found.sign_count, found.last_used = count, security._now()
    security.save_passkeys(items)
    security.succeeded(client)
    token = secrets.token_urlsafe(24)
    _unlocked[token] = time.monotonic() + UNLOCK_SECONDS
    return {"token": token, "seconds": UNLOCK_SECONDS}


@router.post("/lock")
def lock(x_mind_unlock: str = Header(default="")) -> dict[str, Any]:
    _unlocked.pop(x_mind_unlock, None)
    return {"locked": True}


@router.get("/journal", dependencies=[Depends(require_unlocked)])
def journal_list() -> dict[str, Any]:
    return {"journal": service.journal()}


@router.post("/journal")
def journal(body: JournalIn) -> dict[str, Any]:
    return service.add_journal(body.kind, body.text, {k[:20]: v[:500] for k, v in body.extra.items()})


@router.delete("/journal/{entry_id}", dependencies=[Depends(require_unlocked)])
def delete_journal(entry_id: str) -> dict[str, Any]:
    if not service.delete_journal(entry_id):
        raise HTTPException(status_code=404, detail="No such entry.")
    return {"deleted": entry_id}


@router.post("/sessions")
def session(body: SessionIn) -> dict[str, Any]:
    return service.add_session(body.tool, body.seconds)


@router.get("/clarity", dependencies=[Depends(require_unlocked)])
def clarity() -> dict[str, Any]:
    return service.clarity()


@router.post("/clarity/start", dependencies=[Depends(require_unlocked)])
def start(body: StartIn) -> dict[str, Any]:
    return service.start(body.date)


@router.post("/clarity/check", dependencies=[Depends(require_unlocked)])
def check(body: CheckIn) -> dict[str, Any]:
    return service.check(body.status, body.note)


@router.post("/clarity/urge", dependencies=[Depends(require_unlocked)])
def urge(body: UrgeIn) -> dict[str, Any]:
    return service.urge(body.trigger.strip(), body.outcome, body.note)


@router.put("/clarity/plan", dependencies=[Depends(require_unlocked)])
def plan(body: PlanIn) -> dict[str, Any]:
    return service.set_plan(body.reasons, body.plan)


class NudgeIn(BaseModel):
    on: bool


@router.put("/clarity/nudge", dependencies=[Depends(require_unlocked)])
def nudge(body: NudgeIn) -> dict[str, Any]:
    return service.set_nudge(body.on)


class HabitIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class HabitCheck(BaseModel):
    done: bool = True
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class HabitChange(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    archived: bool | None = None


@router.get("/habits")
def habits() -> dict[str, Any]:
    return {"habits": service.habits()}


@router.post("/habits")
def add_habit(body: HabitIn) -> dict[str, Any]:
    return {"habits": service.add_habit(body.name)}


@router.post("/habits/{habit_id}/check")
def check_habit(habit_id: str, body: HabitCheck) -> dict[str, Any]:
    if body.date and body.date > service.today().isoformat():
        raise HTTPException(status_code=422, detail="That day hasn't happened yet.")
    out = service.mark_habit(habit_id, body.done, body.date)
    if out is None:
        raise HTTPException(status_code=404, detail="No such habit.")
    return {"habits": out}


@router.patch("/habits/{habit_id}")
def change_habit(habit_id: str, body: HabitChange) -> dict[str, Any]:
    out = service.change_habit(habit_id, body.name, body.archived)
    if out is None:
        raise HTTPException(status_code=404, detail="No such habit.")
    return {"habits": out}
