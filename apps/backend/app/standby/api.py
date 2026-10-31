"""The standby killer's switches (6.4).

    GET /api/v1/standby            {switches, hours, suggestions: [{sensor, name, watts, switch}]}
    PUT /api/v1/standby            {switches: [switch.*]}
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import require_user
from app.hub import sirisai_api
from app.hub.service import Hub, get_hub
from app.power import service as power
from app.standby import service
from app.tasks import service as tasks

router = APIRouter(prefix="/api/v1/standby", tags=["standby"], dependencies=[Depends(require_user)])


class Switches(BaseModel):
    switches: list[str] = Field(default_factory=list, max_length=40)


@router.get("")
async def get_standby(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    doc = service.load()
    on = power.always_on(power.load()["days"], tasks.today()) or {}
    controls = await sirisai_api.get(hub, "/siris/hub/v1/controls") or {}
    switches = [c["entity_id"] for c in controls.get("controls") or [] if c.get("kind") == "switch"]
    a, b = service.hours()
    return {"switches": doc["switches"], "hours": f"{a}-{b}", "suggestions": service.suggestions(on.get("devices") or [], switches),
            "off_now": doc["off_by_us"]}


@router.put("")
def put_standby(body: Switches) -> dict[str, Any]:
    doc = service.load()
    doc["switches"] = sorted({s for s in body.switches if s.startswith("switch.")})
    doc["off_by_us"] = [s for s in doc["off_by_us"] if s in doc["switches"]]
    service.save(doc)
    return {"switches": doc["switches"]}
