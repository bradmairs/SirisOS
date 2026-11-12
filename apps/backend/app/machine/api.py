"""GET /api/v1/machine: the server's disks and what Ollama has on the GPU (8.9). ?fresh=1 checks now."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.auth import require_user
from app.machine import service

router = APIRouter(prefix="/api/v1/machine", tags=["machine"], dependencies=[Depends(require_user)])


@router.get("")
async def get_machine(fresh: bool = False) -> dict[str, Any]:
    return await service.status(force=fresh)
