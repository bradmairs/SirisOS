"""Yearly goals (4.4). See service.py.

    GET    /api/v1/goals?year=          the year's goals with progress (default: this year)
    POST   /api/v1/goals?year=          {title, kind, target?, unit?, notes?}
    PATCH  /api/v1/goals/{id}?year=     {title?, target?, progress?, done?, notes?}
    DELETE /api/v1/goals/{id}?year=
    GET    /api/v1/goals/prompt             (8.3) what SirisAI asks on Home: set this year's goals, or review a year's
    POST   /api/v1/goals/set?year=          (8.3) "I've set my goals": the January prompt stops
    POST   /api/v1/goals/review?year=       (8.3) {carry: [ids]}: finish the review; those goals start again next year
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from app.auth import require_user
from app.goals import service
from app.hub.service import Hub, get_hub
from app.tasks import service as tasks

router = APIRouter(prefix="/api/v1/goals", tags=["goals"], dependencies=[Depends(require_user)])

Year = Query(default=None, ge=2000, le=2100)


class Change(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    target: float | None = Field(default=None, gt=0, le=1_000_000)
    unit: str | None = Field(default=None, max_length=20)
    progress: float | None = Field(default=None, ge=0, le=1_000_000)
    done: bool | None = None
    notes: str | None = Field(default=None, max_length=1000)


def _year(year: int | None) -> int:
    return year or tasks.today().year


class Review(BaseModel):
    carry: list[str] = Field(default_factory=list, max_length=100)


@router.get("/prompt")
def goals_prompt() -> dict[str, Any]:
    return {"prompt": service.prompt(tasks.today())}


@router.post("/set")
def goals_set(year: int | None = Year) -> dict[str, Any]:
    service.mark("set", _year(year))
    return {"prompt": service.prompt(tasks.today())}


@router.post("/review")
def goals_review(body: Review, year: int | None = Year) -> dict[str, Any]:
    y = _year(year)
    moved = service.carry(y, body.carry)
    service.mark("review", y)
    return {"carried": [g.model_dump() for g in moved], "into": y + 1, "prompt": service.prompt(tasks.today())}


@router.get("")
async def list_goals(year: int | None = Year, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.overview(hub, _year(year))


@router.post("")
def add_goal(goal: service.Goal, year: int | None = Year) -> dict[str, Any]:
    if goal.kind != "done" and not goal.target:
        raise HTTPException(status_code=422, detail="Give the goal a number to reach, e.g. 1000 km.")
    return service.add(_year(year), goal).model_dump()


@router.patch("/{goal_id}")
def change_goal(goal_id: str, body: Change, year: int | None = Year) -> dict[str, Any]:
    try:
        return service.update(_year(year), goal_id, body.model_dump(exclude_none=True)).model_dump()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="No such goal.") from exc


@router.delete("/{goal_id}", status_code=204, response_class=Response)
def delete_goal(goal_id: str, year: int | None = Year) -> Response:
    try:
        service.delete(_year(year), goal_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="No such goal.") from exc
    return Response(status_code=204)
