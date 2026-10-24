"""The house (4.5): where each device sits in the 3D model.

    GET /api/v1/house/placements    {placements: {device id: {room, x?, z?, hidden?}}}
    PUT /api/v1/house/placements    replace them

Device ids are UniFi MACs (from SirisAI's /siris/hub/v1/network, relayed at
/api/v1/assistant/network) or Home Assistant entity ids. A device with no
placement is put in a room by its name (apps/web/src/house/placement.ts).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import require_user
from app.services import json_store

router = APIRouter(prefix="/api/v1/house", tags=["house"], dependencies=[Depends(require_user)])


class Placement(BaseModel):
    room: str = Field(min_length=1, max_length=40)
    x: float | None = Field(default=None, ge=-20, le=40)
    z: float | None = Field(default=None, ge=-20, le=40)
    hidden: bool = False


class Placements(BaseModel):
    placements: dict[str, Placement] = Field(default_factory=dict, max_length=500)


def _path():
    return json_store.data_path("SIRISOS_HOUSE_PATH", "house.json")


@router.get("/placements")
def get_placements() -> dict[str, Any]:
    raw = json_store.read(_path(), {})
    return Placements.model_validate(raw if isinstance(raw, dict) else {}).model_dump(exclude_none=True)


@router.put("/placements")
def put_placements(body: Placements) -> dict[str, Any]:
    json_store.write(_path(), body.model_dump(exclude_none=True))
    return body.model_dump(exclude_none=True)
