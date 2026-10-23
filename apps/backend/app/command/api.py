"""Talk to SirisOS (4.3). See service.py.

    POST /api/v1/command   {text}: do it -> {intent, reply, link, ...}
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import require_user
from app.command import service
from app.hub.service import Hub, get_hub

router = APIRouter(prefix="/api/v1/command", tags=["command"], dependencies=[Depends(require_user)])


class Command(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


@router.post("")
async def command(body: Command, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.run(hub, body.text)
