"""Resurfacing (5.1). See service.py.

    GET  /api/v1/resurface              today's older note (or null)
    POST /api/v1/resurface/respond      {title, answer: "seen" | "not_useful"}
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import require_user
from app.hub.service import Hub, get_hub
from app.resurface import service

router = APIRouter(prefix="/api/v1/resurface", tags=["resurface"], dependencies=[Depends(require_user)])


class Answer(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    answer: Literal["seen", "not_useful"]


@router.get("")
async def get_today(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    result = await service.today_note(hub)
    note = result["note"]
    return {"note": None if not note or note.get("seen") else note}


@router.post("/respond")
async def respond(body: Answer, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.respond(hub, body.title, body.answer)
