"""GET /api/v1/updates (?fresh=1): the running version, main's on GitHub, and the last update's log (11.11).
Updating runs through the Terminal: POST /api/v1/terminal/run with the builtin:update-sirisos shortcut."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.auth import require_user
from app.updates import service

router = APIRouter(prefix="/api/v1/updates", tags=["updates"], dependencies=[Depends(require_user)])


@router.get("")
def get_updates(fresh: bool = False) -> dict[str, Any]:
    """The running version against main's on GitHub, and the last update's log."""
    return service.status(force=fresh)
