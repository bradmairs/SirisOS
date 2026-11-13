"""Documents and renewals (9.3). See service.py.

    GET    /api/v1/renewals             soonest first, each with days_left and state (expired, soon, later, fine)
    POST   /api/v1/renewals             {name, kind, expires, note?}
    PATCH  /api/v1/renewals/{id}        {name?, kind?, expires?, note?}: renewed, so a new date
    DELETE /api/v1/renewals/{id}
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_user
from app.renewals import service

router = APIRouter(prefix="/api/v1/renewals", tags=["renewals"], dependencies=[Depends(require_user)])
Kind = Literal["passport", "licence", "rego", "insurance", "medicare", "warranty", "membership", "other"]
DAY = r"^\d{4}-\d{2}-\d{2}$"


class NewRenewal(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: Kind = "other"
    expires: str = Field(pattern=DAY)
    note: str = Field(default="", max_length=300)


class RenewalChange(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    kind: Kind | None = None
    expires: str | None = Field(default=None, pattern=DAY)
    note: str | None = Field(default=None, max_length=300)


@router.get("")
def listing() -> dict[str, Any]:
    return {"renewals": service.listing()}


@router.post("")
def add(body: NewRenewal) -> dict[str, Any]:
    return {"renewals": service.add(body.name, body.kind, body.expires, body.note)}


@router.patch("/{item_id}")
def change(item_id: str, body: RenewalChange) -> dict[str, Any]:
    out = service.change(item_id, **body.model_dump())
    if out is None:
        raise HTTPException(status_code=404, detail="No such renewal.")
    return {"renewals": out}


@router.delete("/{item_id}")
def remove(item_id: str) -> dict[str, Any]:
    if not service.remove(item_id):
        raise HTTPException(status_code=404, detail="No such renewal.")
    return {"renewals": service.listing()}
