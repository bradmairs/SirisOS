"""Home Lab (8.5). See service.py.

    GET    /api/v1/homelab           the diagram: nodes (id, label, kind, parent, online, model, notes, detail), device counts
    PATCH  /api/v1/homelab/{id}      {label?, model?, notes?, parent?, kind?}: your details for a box ("" clears)
    POST   /api/v1/homelab           {label, kind, parent?}: hardware SirisOS can't see
    DELETE /api/v1/homelab/{id}      one you added
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_user
from app.homelab import service
from app.hub.service import Hub, get_hub

router = APIRouter(prefix="/api/v1/homelab", tags=["homelab"], dependencies=[Depends(require_user)])
Kind = Literal["internet", "modem", "gateway", "switch", "access_point", "server", "nas", "ups", "docker", "device", "other"]


class NodeChange(BaseModel):
    label: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=300)
    parent: str | None = Field(default=None, max_length=120)
    kind: Kind | None = None


class NewNode(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    kind: Kind = "other"
    parent: str | None = Field(default=None, max_length=120)


@router.get("")
async def diagram(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.diagram(hub)


@router.patch("/{node_id:path}")
async def change(node_id: str, body: NodeChange, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    if body.parent == node_id:
        raise HTTPException(status_code=422, detail="It can't plug into itself.")
    service.update(node_id, body.model_dump())
    return await service.diagram(hub)


@router.post("")
async def add(body: NewNode, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    service.add(body.label, body.kind, body.parent)
    return await service.diagram(hub)


@router.delete("/{node_id:path}")
async def remove(node_id: str, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    if not service.remove(node_id):
        raise HTTPException(status_code=404, detail="Only hardware you added can be removed.")
    return await service.diagram(hub)
