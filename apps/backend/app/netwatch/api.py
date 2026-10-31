"""Network alerts (5.3). See service.py.

    GET  /api/v1/netwatch                       every device seen: new, important, blocked, offline
    POST /api/v1/netwatch/{id}/trust            it's ours: stop asking
    POST /api/v1/netwatch/{id}/important        {important: bool}
    PATCH /api/v1/netwatch/{id}                 {label, owner, type}: the inventory (6.2)
    POST /api/v1/netwatch/{id}/block            {blocked: bool}, through SirisAI and UniFi
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_user
from app.hub.service import Hub, get_hub
from app.hub.sirisai_api import SirisAIError
from app.netwatch import service

router = APIRouter(prefix="/api/v1/netwatch", tags=["netwatch"], dependencies=[Depends(require_user)])


class Important(BaseModel):
    important: bool


class Details(BaseModel):
    label: str | None = Field(default=None, max_length=60)
    owner: str | None = Field(default=None, max_length=60)
    type: str | None = Field(default=None, max_length=40)


class Blocked(BaseModel):
    blocked: bool


@router.get("")
def get_view() -> dict[str, Any]:
    return service.view()


@router.post("/{node_id}/trust")
def trust(node_id: str) -> dict[str, Any]:
    try:
        service.trust(node_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="SirisOS hasn't seen that device.") from None
    return service.view()


@router.post("/{node_id}/important")
def important(node_id: str, body: Important) -> dict[str, Any]:
    try:
        service.set_important(node_id, body.important)
    except LookupError:
        raise HTTPException(status_code=404, detail="SirisOS hasn't seen that device.") from None
    return service.view()


@router.patch("/{node_id}")
def details(node_id: str, body: Details) -> dict[str, Any]:
    """Name it, say whose it is and what it is (6.2); its room comes from the 3D house."""
    try:
        service.set_details(node_id, body.model_dump(exclude_unset=True))
    except LookupError:
        raise HTTPException(status_code=404, detail="SirisOS hasn't seen that device.") from None
    return service.view()


@router.post("/{node_id}/block")
async def block(node_id: str, body: Blocked, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    try:
        await service.set_blocked(hub, node_id, body.blocked)
    except SirisAIError as exc:
        raise HTTPException(status_code=exc.status if exc.status < 500 else 502, detail=str(exc)) from None
    return service.view()
