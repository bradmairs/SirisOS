"""Backups of SirisOS's own data (3.7).

    GET  /api/v1/backups                  status and every backup, newest first
    POST /api/v1/backups                  make one now
    GET  /api/v1/backups/{name}           download it
    POST /api/v1/backups/{name}/restore   {confirm: "restore"}: put it back (a backup of now is taken first)
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.auth import require_user
from app.backup import service

router = APIRouter(prefix="/api/v1/backups", tags=["backups"], dependencies=[Depends(require_user)])


class Restore(BaseModel):
    confirm: str


@router.get("")
def list_backups() -> dict[str, Any]:
    return {**service.status(), "backups": service.backups()}


@router.post("")
async def make_backup() -> dict[str, Any]:
    try:
        return await asyncio.to_thread(service.create, "manual")
    except OSError as exc:
        raise HTTPException(status_code=503, detail=f"Couldn't write the backup to {service.backup_dir()}: {exc.strerror or exc}") from exc


@router.get("/{name}")
def download(name: str) -> FileResponse:
    try:
        return FileResponse(service.path_of(name), media_type="application/gzip", filename=name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No such backup.") from exc


@router.post("/{name}/restore")
async def restore(name: str, body: Restore) -> dict[str, Any]:
    if body.confirm != "restore":
        raise HTTPException(status_code=400, detail='Type "restore" to confirm.')
    try:
        return await asyncio.to_thread(service.restore, name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No such backup.") from exc
    except (ValueError, KeyError, OSError) as exc:
        raise HTTPException(status_code=422, detail=f"That backup can't be restored: {exc}") from exc
