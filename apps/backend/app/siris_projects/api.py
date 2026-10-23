"""Projects (4.0). See service.py.

    GET  /api/v1/siris-projects                 every Siris project: due, quiet, open tasks
    GET  /api/v1/siris-projects/{title}         one project's page
    POST /api/v1/siris-projects/{title}/done    mark the project finished in Siris
    POST /api/v1/siris-projects/{title}/tasks   {text}: a SirisOS task for it
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_user
from app.hub.service import Hub, get_hub
from app.hub.sirisai_api import SirisAIError
from app.siris_projects import service
from app.tasks import service as tasks

router = APIRouter(prefix="/api/v1/siris-projects", tags=["projects"], dependencies=[Depends(require_user)])


class NewTask(BaseModel):
    text: str = Field(min_length=1, max_length=300)


@router.get("")
async def list_projects(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.overview(hub)


@router.get("/{title}")
async def get_project(title: str, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    try:
        return await service.page(hub, title)
    except service.NotFound as exc:
        raise HTTPException(status_code=404, detail=f"No project called {title!r} in Siris.") from exc


@router.post("/{title}/done")
async def finish(title: str, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    try:
        return await service.finish(hub, title)
    except SirisAIError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc


@router.post("/{title}/tasks")
def add_task(title: str, body: NewTask) -> dict[str, Any]:
    """Plain words like the Tasks screen ("send levels friday"); the project's
    name goes in the notes, so it shows on this page."""
    task = tasks.parse(body.text)
    task.notes = (task.notes + " · " if task.notes else "") + f"Project: {title}"
    return tasks.add(task).model_dump()
