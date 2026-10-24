"""Home layout API: GET and PUT the whole layout (it's small)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import require_user
from app.home import context, schedule, store
from app.hub.service import Hub, get_hub

router = APIRouter(prefix="/api/v1/home", tags=["home"], dependencies=[Depends(require_user)])


@router.get("/layout")
async def get_layout() -> store.HomeLayout:
    return store.load()


@router.put("/layout")
async def put_layout(layout: store.HomeLayout) -> store.HomeLayout:
    return store.save(layout)


@router.get("/schedule")
async def get_schedule() -> schedule.Schedule:
    return schedule.load()


@router.put("/schedule")
async def put_schedule(body: schedule.Schedule) -> schedule.Schedule:
    return schedule.save(body)


@router.get("/context")
async def get_context(hub: Hub = Depends(get_hub)) -> dict:
    """What part of the day it is (and whether anyone's home), so Home can put
    the right things first: morning, work, evening, night or weekend."""
    return await context.current(hub)
