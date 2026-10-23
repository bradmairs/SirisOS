"""Meeting prep API (3.2).

    GET  /api/v1/meetings                       today's and tomorrow's timed meetings still to come
    GET  /api/v1/meetings/prep?title=&start=    related Siris notes, the latest emails from the attendees, related tasks
    POST /api/v1/meetings/notes                 {title, start, text}: file into Siris; "- [ ]" lines become tasks
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import require_user
from app.hub import sirisai_api
from app.hub.service import Hub, get_hub
from app.meetings import service

router = APIRouter(prefix="/api/v1/meetings", tags=["meetings"], dependencies=[Depends(require_user)])


class Notes(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    start: str | None = Field(default=None, max_length=40)
    text: str = Field(min_length=1, max_length=20000)


@router.get("")
async def list_meetings(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return {"meetings": await service.upcoming(hub)}


@router.get("/prep")
async def meeting_prep(title: str = Query(min_length=1, max_length=300), start: str | None = Query(None, max_length=40), hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.prep(hub, title, start)


@router.post("/notes")
async def meeting_notes(body: Notes, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    try:
        return await service.save_notes(hub, body.title, body.start, body.text)
    except sirisai_api.SirisAIError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from None
