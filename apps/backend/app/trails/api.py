"""SirisTrails (11.22). See service.py.

    GET    /api/v1/trails?year=          walks and hikes (with each one's map line) and the totals
    GET    /api/v1/trails/{id}           one walk: its full route and elevation profile
    PATCH  /api/v1/trails/{id}           {name, note}
    DELETE /api/v1/trails/{id}           delete it (and don't bring it back on a later import)
    POST   /api/v1/trails/apple-export   the Apple Health export.zip (multipart `file`): every walk and hike, in the background
    GET    /api/v1/trails/import         how the last export upload went
"""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile
from pydantic import BaseModel, Field

from app.auth import require_user
from app.trails import service

router = APIRouter(prefix="/api/v1/trails", tags=["trails"], dependencies=[Depends(require_user)])
MAX_EXPORT_BYTES = 8 * 1024 ** 3
WALK_ID = r"^w_[0-9a-f]{12}$"


@router.get("")
def walks(year: int | None = Query(None, ge=1990, le=2100)) -> dict[str, Any]:
    return service.summary(year)


@router.get("/import")
def import_status() -> dict[str, Any]:
    return service.import_status()


@router.post("/apple-export")
async def apple_export(file: UploadFile = File(...)) -> dict[str, Any]:
    if service.import_status().get("running"):
        raise HTTPException(status_code=409, detail="An import is already running.")
    folder = service.root()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"incoming-{secrets.token_hex(4)}.zip"
    size = 0
    with path.open("wb") as out:
        while chunk := await file.read(8 * 1024 * 1024):
            size += len(chunk)
            if size > MAX_EXPORT_BYTES:
                out.close()
                path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="That's over 8 GB.")
            out.write(chunk)
    with path.open("rb") as fh:
        if fh.read(2) != b"PK":
            path.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail="That isn't a zip: upload export.zip from the Health app as it is.")
    service.start_apple_import(path)
    return {"started": True, "bytes": size}


@router.get("/{walk_id}")
def walk(walk_id: str = Path(pattern=WALK_ID)) -> dict[str, Any]:
    try:
        return service.detail(walk_id)
    except (KeyError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="No such walk.") from None


class WalkChange(BaseModel):
    name: str | None = Field(None, max_length=120)
    note: str | None = Field(None, max_length=2000)


@router.patch("/{walk_id}")
def change(body: WalkChange, walk_id: str = Path(pattern=WALK_ID)) -> dict[str, Any]:
    try:
        return service.change(walk_id, body.name, body.note)
    except KeyError:
        raise HTTPException(status_code=404, detail="No such walk.") from None


@router.delete("/{walk_id}")
def remove(walk_id: str = Path(pattern=WALK_ID)) -> dict[str, bool]:
    try:
        service.delete(walk_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="No such walk.") from None
    return {"ok": True}
