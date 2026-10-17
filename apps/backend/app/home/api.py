"""Home layout API: GET and PUT the whole layout (it's small)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import require_user
from app.home import store

router = APIRouter(prefix="/api/v1/home", tags=["home"], dependencies=[Depends(require_user)])


@router.get("/layout")
async def get_layout() -> store.HomeLayout:
    return store.load()


@router.put("/layout")
async def put_layout(layout: store.HomeLayout) -> store.HomeLayout:
    return store.save(layout)
