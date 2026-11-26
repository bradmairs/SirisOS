"""The Server handbook (11.9): your own commands, beside the built-in ones in the app.

    GET    /api/v1/handbook              {entries: [{id, cmd, what, section}]}
    POST   /api/v1/handbook              {cmd, what, section?}
    PATCH  /api/v1/handbook/{id}         {cmd?, what?, section?}
    DELETE /api/v1/handbook/{id}
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_user
from app.handbook import service

router = APIRouter(prefix="/api/v1/handbook", tags=["handbook"], dependencies=[Depends(require_user)])


class EntryIn(BaseModel):
    cmd: str = Field(min_length=1, max_length=2000)
    what: str = Field(default="", max_length=300)
    section: str = Field(default="Mine", max_length=40)


class EntryChange(BaseModel):
    cmd: str | None = Field(default=None, min_length=1, max_length=2000)
    what: str | None = Field(default=None, max_length=300)
    section: str | None = Field(default=None, max_length=40)


@router.get("")
def list_entries() -> dict[str, Any]:
    """Your own handbook commands."""
    return {"entries": service.entries()}


@router.post("")
def add_entry(body: EntryIn) -> dict[str, Any]:
    """Add a command of your own to the handbook."""
    return {"entries": service.add(body.cmd, body.what, body.section)}


@router.patch("/{entry_id}")
def change_entry(entry_id: str, body: EntryChange) -> dict[str, Any]:
    """Change one of your handbook commands."""
    out = service.change(entry_id, body.cmd, body.what, body.section)
    if out is None:
        raise HTTPException(status_code=404, detail="No such command.")
    return {"entries": out}


@router.delete("/{entry_id}")
def delete_entry(entry_id: str) -> dict[str, Any]:
    """Take one of your commands out of the handbook."""
    out = service.remove(entry_id)
    if out is None:
        raise HTTPException(status_code=404, detail="No such command.")
    return {"entries": out}
