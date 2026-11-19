"""Trips (10.2). See service.py.

    GET    /api/v1/travel             every trip, soonest first, the next or current one in full
    POST   /api/v1/travel             {destination, start, end, notes?}: the place is looked up and a packing list made
    GET    /api/v1/travel/current     the trip for Home (a week before until it ends), in full, or null
    PATCH  /api/v1/travel/{id}        {packing?, ooo_done?, notes?}
    DELETE /api/v1/travel/{id}
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_user
from app.brief.service import zone
from app.travel import service

router = APIRouter(prefix="/api/v1/travel", tags=["travel"], dependencies=[Depends(require_user)])
_ID = re.compile(r"[a-f0-9]{10}")


def _today() -> date:
    return datetime.now(zone()).date()


def _trip(trip_id: str) -> str:
    if not _ID.fullmatch(trip_id):
        raise HTTPException(status_code=404, detail="No such trip.")
    return trip_id


@router.get("")
async def trips() -> dict[str, Any]:
    today = _today()
    upcoming = [t for t in service.load() if t["end"] >= today.isoformat()]
    past = [t for t in service.load() if t["end"] < today.isoformat()]
    return {"next": await service.view(upcoming[0], today) if upcoming else None, "upcoming": upcoming, "past": past[-10:][::-1]}


class TripIn(BaseModel):
    destination: str = Field(..., min_length=1, max_length=80)
    start: date
    end: date
    notes: str = Field("", max_length=500)


@router.post("")
async def add_trip(body: TripIn) -> dict[str, Any]:
    try:
        trip = await service.add(body.destination, body.start, body.end, body.notes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return await service.view(trip, _today())


@router.get("/current")
async def current() -> dict[str, Any]:
    today = _today()
    trip = service.current(today)
    return {"trip": await service.view(trip, today) if trip else None}


class PackItem(BaseModel):
    item: str = Field(..., max_length=80)
    done: bool = False


class TripChange(BaseModel):
    packing: list[PackItem] | None = Field(None, max_length=80)
    ooo_done: bool | None = None
    notes: str | None = Field(None, max_length=500)


@router.patch("/{trip_id}")
async def change_trip(trip_id: str, body: TripChange) -> dict[str, Any]:
    trip = service.change(_trip(trip_id), {"packing": [p.model_dump() for p in body.packing] if body.packing is not None else None,
                                           "ooo_done": body.ooo_done, "notes": body.notes})
    if trip is None:
        raise HTTPException(status_code=404, detail="No such trip.")
    return await service.view(trip, _today())


@router.delete("/{trip_id}")
def delete_trip(trip_id: str) -> dict[str, Any]:
    if not service.remove(_trip(trip_id)):
        raise HTTPException(status_code=404, detail="No such trip.")
    return {"removed": True}
