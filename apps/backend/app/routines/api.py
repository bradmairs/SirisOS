"""10.4: the weekend planner, garden and rain, fuel on the way to Shepparton, bin night, the bedroom before bed,
what to watch tonight (and new episodes), container updates, internet speed, and catch-ups.

    GET  /api/v1/weekend                 Saturday and Sunday's best windows outside, each with one of your routes
    PUT  /api/v1/weekend/routes          {routes: [{name, kind, hours, km?, link?, notes?}]}
    GET  /api/v1/garden                  water today or not, and why; PUT {on?, protocol?}; POST /garden/watered
    GET  /api/v1/fuel                    the cheapest fuel within the first 30 km of the drive; PUT /fuel/settings
    GET  /api/v1/bins                    next collection and which bins; PUT {bins: [{kind, every_weeks, first}]}
    GET  /api/v1/bedroom                 the bedroom now, against your range, and which temperatures go with good sleep; PUT settings
    GET  /api/v1/watch/tonight           picks for tonight, Plex on deck and new, episodes and films coming this week
    GET  /api/v1/lab/containers          container updates (SirisAI 7.3); POST /lab/containers/check; POST /lab/containers/update {containers?}
    GET  /api/v1/lab/containers/history  (11.19) updates, roll-backs and failures; POST /lab/containers/{name}/roll-back|update
    GET  /api/v1/lab/internet            speed tests and drops, by day, against your plan; PUT /lab/internet/plan {down, up}
    GET  /api/v1/catchups                who's overdue for a catch-up, and the weekend's free parts; POST /catchups/{id}/done; PUT /catchups/{id} {days}
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from app.auth import require_user
from app.brief.service import zone
from app.household import bedroom, bins
from app.hub import sirisai_api
from app.hub.service import Hub, get_hub
from app.outdoors import fuel, garden, weekend
from app.routines import catchups, lab

router = APIRouter(prefix="/api/v1", tags=["routines"], dependencies=[Depends(require_user)])
_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9 _'&-]{0,79}")


def _now() -> datetime:
    return datetime.now(zone())


def _fail(exc: sirisai_api.SirisAIError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=str(exc))


# -- weekend --------------------------------------------------------------------------------------------------

class Route(BaseModel):
    id: str | None = Field(None, max_length=20)
    name: str = Field(..., min_length=1, max_length=80)
    kind: Literal["run", "hike", "ride", "walk", "other"] = "other"
    hours: float = Field(1.0, gt=0, le=12)
    km: float | None = Field(None, ge=0, le=500)
    link: str | None = Field(None, max_length=300)
    notes: str = Field("", max_length=200)


class Routes(BaseModel):
    routes: list[Route] = Field(..., max_length=40)


@router.get("/weekend")
async def get_weekend(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await weekend.plan(hub, _now().date())


@router.put("/weekend/routes")
async def put_routes(body: Routes, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    for r in body.routes:
        if r.link and not r.link.startswith(("https://", "http://")):
            raise HTTPException(status_code=422, detail="A link starts with https://")
    weekend.set_routes([r.model_dump() for r in body.routes])
    return await weekend.plan(hub, _now().date())


# -- garden ---------------------------------------------------------------------------------------------------

class GardenIn(BaseModel):
    on: bool | None = None
    protocol: str | None = Field(None, max_length=80)


@router.get("/garden")
async def get_garden(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await garden.today_check(hub, _now().date())


@router.put("/garden")
async def put_garden(body: GardenIn, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    if body.protocol and not _NAME.fullmatch(body.protocol):
        raise HTTPException(status_code=422, detail="That isn't a protocol name.")
    garden.save_settings(body.on, body.protocol)
    return await garden.today_check(hub, _now().date())


@router.post("/garden/watered")
async def post_watered(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    garden.watered(_now().date())
    return await garden.today_check(hub, _now().date())


# -- fuel -----------------------------------------------------------------------------------------------------

class Place(BaseModel):
    name: str = Field("", max_length=80)
    lat: float = Field(..., ge=-44, le=-10)
    lon: float = Field(..., ge=112, le=154)


class FuelSettings(BaseModel):
    on: bool | None = None
    weekday: int | None = Field(None, ge=0, le=6)
    leave: str | None = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    fuel_type: Literal["U91", "E10", "P95", "P98", "DSL", "LPG"] | None = None
    first_km: float | None = Field(None, ge=2, le=200)
    off_route_km: float | None = Field(None, ge=0.2, le=10)
    destination: Place | None = None
    home: Place | None = None


@router.get("/fuel")
async def get_fuel(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    out = await fuel.suggest(hub)
    return {**out, "for": (d.isoformat() if (d := fuel.due(_now(), out["settings"])) else None)}


@router.put("/fuel/settings")
async def put_fuel(body: FuelSettings, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    try:
        fuel.save_settings(body.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return await get_fuel(hub)


# -- bins -----------------------------------------------------------------------------------------------------

class Bin(BaseModel):
    kind: Literal["rubbish", "recycling", "green", "glass"]
    every_weeks: Literal[1, 2, 4]
    first: date


class Bins(BaseModel):
    bins: list[Bin] = Field(..., max_length=6)


@router.get("/bins")
def get_bins() -> dict[str, Any]:
    return bins.card(_now())


@router.put("/bins")
def put_bins(body: Bins) -> dict[str, Any]:
    bins.save([b.model_dump() for b in body.bins])
    return bins.card(_now())


# -- bedroom --------------------------------------------------------------------------------------------------

class BedroomIn(BaseModel):
    temp_entity: str | None = Field(None, max_length=110)
    humidity_entity: str | None = Field(None, max_length=110)
    low: float | None = Field(None, ge=10, le=30)
    high: float | None = Field(None, ge=10, le=30)


@router.get("/bedroom")
async def get_bedroom(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await bedroom.card(hub, _now())


@router.put("/bedroom")
async def put_bedroom(body: BedroomIn, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    try:
        bedroom.save_settings(body.temp_entity, body.humidity_entity, body.low, body.high)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return await bedroom.card(hub, _now())


# -- watch ----------------------------------------------------------------------------------------------------

@router.get("/watch/tonight")
async def get_watch(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    from app.evenings import watch

    return await watch.tonight(hub, _now())


# -- lab ------------------------------------------------------------------------------------------------------

@router.get("/lab/containers")
async def get_containers(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    body = await sirisai_api.get(hub, "/siris/hub/v1/containers", timeout=15.0)
    return body if isinstance(body, dict) else {"available": False, "updates": [], "up_to_date": [], "skipped": {}}


@router.post("/lab/containers/check")
async def check_containers(hub: Hub = Depends(get_hub)) -> Any:
    try:
        return await sirisai_api.post(hub, "/siris/hub/v1/containers/check", json={}, timeout=300.0)
    except sirisai_api.SirisAIError as exc:
        raise _fail(exc) from None


class UpdateIn(BaseModel):
    containers: list[str] | None = Field(None, max_length=100)


@router.post("/lab/containers/update")
async def update_containers(body: UpdateIn, hub: Hub = Depends(get_hub)) -> Any:
    try:
        return await sirisai_api.post(hub, "/siris/hub/v1/containers/update", json=body.model_dump(), timeout=30.0)
    except sirisai_api.SirisAIError as exc:
        raise _fail(exc) from None


@router.get("/lab/containers/history")
async def container_history(hub: Hub = Depends(get_hub)) -> Any:
    """11.19 (SirisAI 4.32): every update, roll-back and failure, with what each was on before, and the ones held back."""
    try:
        return await sirisai_api.get(hub, "/siris/upkeep/containers", timeout=15.0)
    except sirisai_api.SirisAIError as exc:
        raise _fail(exc) from None


@router.post("/lab/containers/{name}/{action}")
async def container_action(name: str = Path(max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"),
                           action: str = Path(pattern=r"^(roll-back|update)$"), hub: Hub = Depends(get_hub)) -> Any:
    """`roll-back`: back to the version before its last update, held there; `update`: update it now (and release it)."""
    try:
        return await sirisai_api.post(hub, f"/siris/upkeep/containers/{name}/{action}", json={}, timeout=30.0)
    except sirisai_api.SirisAIError as exc:
        raise _fail(exc) from None


@router.get("/lab/internet")
async def get_internet(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await lab.internet(hub, 30)


class PlanIn(BaseModel):
    down: float | None = Field(None, gt=0, le=10000)
    up: float | None = Field(None, gt=0, le=10000)


@router.put("/lab/internet/plan")
async def put_plan(body: PlanIn, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    lab.set_plan(body.down, body.up)
    return await lab.internet(hub, 30)


# -- catch-ups ------------------------------------------------------------------------------------------------

@router.get("/catchups")
async def get_catchups(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await catchups.overview(hub, _now().date())


@router.post("/catchups/{person_id}/done")
async def catchup_done(person_id: int, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    try:
        await catchups.caught_up(hub, person_id, _now().date())
    except sirisai_api.SirisAIError as exc:
        raise _fail(exc) from None
    return await catchups.overview(hub, _now().date())


class GapIn(BaseModel):
    days: int | None = Field(None, ge=1, le=730)


@router.put("/catchups/{person_id}")
async def catchup_gap(person_id: int, body: GapIn, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    try:
        await catchups.set_gap(hub, person_id, body.days)
    except sirisai_api.SirisAIError as exc:
        raise _fail(exc) from None
    return await catchups.overview(hub, _now().date())
