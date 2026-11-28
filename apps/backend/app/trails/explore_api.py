"""SirisTrails 12.6. See explore.py. Registered before trails/api.py's /{walk_id} routes.

    GET    /api/v1/trails/home                 the last walk and this year so far, for Home
    GET    /api/v1/trails/streets              the suburbs you walk in most, and how much of each you've walked
    GET    /api/v1/trails/streets/{slug}       one suburb's streets, walked or not, for the map
    GET    /api/v1/trails/wishlist             walks you want to do (ticked off by themselves when you do them)
    GET    /api/v1/trails/wishlist/search?q=   tracks, peaks and parks from OpenStreetMap
    POST   /api/v1/trails/wishlist             {osm: "R1234"}
    DELETE /api/v1/trails/wishlist/{id}
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from app.auth import require_user
from app.trails import explore

router = APIRouter(prefix="/api/v1/trails", tags=["trails"], dependencies=[Depends(require_user)])


@router.get("/home")
def home() -> dict[str, Any] | None:
    return explore.home_card()


@router.get("/streets")
def streets() -> list[dict[str, Any]]:
    return explore.streets_overview()


@router.get("/streets/{slug}")
def street(slug: str = Path(pattern=r"^[a-z0-9-]{1,60}$")) -> dict[str, Any]:
    try:
        return explore.streets_detail(slug)
    except (KeyError, OSError, ValueError):
        raise HTTPException(status_code=404, detail="Those streets haven't been looked up yet.") from None


@router.get("/wishlist")
def wishlist() -> list[dict[str, Any]]:
    return explore.load_wishes()


@router.get("/wishlist/search")
def wishlist_search(q: str = Query(min_length=2, max_length=120)) -> list[dict[str, Any]]:
    try:
        return explore.search(q)
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=502, detail="OpenStreetMap's search didn't answer. Try again in a minute.") from None


class Wish(BaseModel):
    osm: str = Field(pattern=r"^[NWR]\d{1,12}$")


@router.post("/wishlist")
def add_wish(body: Wish) -> dict[str, Any]:
    try:
        return explore.add_wish(body.osm)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="OpenStreetMap didn't answer. Try again in a minute.") from None


@router.delete("/wishlist/{wish_id}")
def remove_wish(wish_id: str = Path(pattern=r"^x_[0-9a-f]{10}$")) -> dict[str, bool]:
    try:
        explore.remove_wish(wish_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Not on the wishlist.") from None
    return {"ok": True}
