"""Meals (10.2). See service.py.

    GET    /api/v1/meals?start=YYYY-MM-DD      seven nights from `start` (today by default), dinners you have often, Mealie's state
    PUT    /api/v1/meals/{date}                plan a dinner (`title`, optional Mealie `slug` and `recipe_id`, or your own `ingredients`)
    DELETE /api/v1/meals/{date}
    GET    /api/v1/meals/recipes?q=            your Mealie recipes
    GET    /api/v1/meals/shopping?start=       the week's ingredients, merged, less staples and what's on the list already
    POST   /api/v1/meals/shopping              `items` onto Home Assistant list `list` (through SirisAI)
    PUT    /api/v1/meals/staples               things you always have, left off the shopping
    GET    /api/v1/meals/tonight               tonight's dinner, for Home
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_user
from app.brief.service import zone
from app.hub import sirisai_api
from app.hub.service import Hub, get_hub
from app.meals import mealie, service

router = APIRouter(prefix="/api/v1/meals", tags=["meals"], dependencies=[Depends(require_user)])

_LIST_ID = re.compile(r"todo\.[a-z0-9_]{1,80}")
_SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,150}")


def _today() -> date:
    from datetime import datetime

    return datetime.now(zone()).date()


def _err(exc: mealie.MealieError) -> HTTPException:
    return HTTPException(status_code=502, detail=str(exc))


@router.get("")
async def get_week(start: date | None = None) -> dict[str, Any]:
    return await service.week(start or _today())


class StaplesIn(BaseModel):
    staples: list[str] = Field(..., max_length=60)


@router.put("/staples")
def put_staples(body: StaplesIn) -> dict[str, Any]:
    return {"staples": service.set_staples(body.staples)}


class DinnerIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    slug: str | None = Field(None, max_length=150)
    recipe_id: str | None = Field(None, max_length=64)
    ingredients: list[str] | None = Field(None, max_length=40)
    start: date | None = None


@router.put("/{on}")
async def put_dinner(on: date, body: DinnerIn) -> dict[str, Any]:
    if body.slug and not _SLUG.fullmatch(body.slug):
        raise HTTPException(status_code=422, detail="That isn't a Mealie recipe.")
    try:
        return await service.plan(on, body.title, body.slug, body.recipe_id, body.ingredients, body.start)
    except mealie.MealieError as exc:
        raise _err(exc) from None


@router.delete("/{on}")
async def delete_dinner(on: date, start: date | None = None) -> dict[str, Any]:
    try:
        return await service.unplan(on, start)
    except mealie.MealieError as exc:
        raise _err(exc) from None


@router.get("/recipes")
async def recipes(q: str = "") -> dict[str, Any]:
    if not mealie.configured():
        return {"configured": False, "recipes": []}
    try:
        return {"configured": True, "recipes": await mealie.search(q.strip()[:80])}
    except mealie.MealieError as exc:
        raise _err(exc) from None


@router.get("/shopping")
async def get_shopping(start: date | None = None, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.shopping(hub, start or _today())


class ShoppingIn(BaseModel):
    items: list[str] = Field(..., min_length=1, max_length=60)
    list_id: str = Field(..., max_length=90, alias="list")


@router.post("/shopping")
async def post_shopping(body: ShoppingIn, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    if not _LIST_ID.fullmatch(body.list_id):
        raise HTTPException(status_code=404, detail="No such list.")
    try:
        added = await service.add_to_list(hub, [i.strip() for i in body.items if i.strip()], body.list_id)
    except sirisai_api.SirisAIError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from None
    return {"added": added, "list": body.list_id}


@router.get("/tonight")
async def get_tonight() -> dict[str, Any]:
    """Tonight's dinner: Mealie's plan when it's set up (so one planned in Mealie shows too), else what was planned here."""
    today = _today()
    if mealie.configured():
        try:
            for p in await mealie.plans(today, today):
                if p["date"] == today.isoformat():
                    return {"dinner": {"title": p["title"], "slug": p.get("slug")}}
        except mealie.MealieError:
            pass
    return {"dinner": service.tonight(today)}
