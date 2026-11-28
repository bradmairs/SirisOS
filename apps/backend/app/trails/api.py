"""SirisTrails (11.22). See service.py.

    GET    /api/v1/trails?year=          walks and hikes (with each one's map line) and the totals
    GET    /api/v1/trails/{id}           one walk: its full route and elevation profile
    PATCH  /api/v1/trails/{id}           {name, note}
    DELETE /api/v1/trails/{id}           delete it (and don't bring it back on a later import)
    POST   /api/v1/trails/apple-export   the Apple Health export.zip (multipart `file`): every walk and hike, in the background
    GET    /api/v1/trails/import         how the last export upload went
    GET    /api/v1/trails/{id}/gpx?hide_home=   12.5: the walk as GPX (without the ends near home, if asked)
    POST   /api/v1/trails/{id}/trim      {from_km, to_km}: cut the start or end (DELETE: undo)
    POST   /api/v1/trails/{id}/join      {other}: add another recording of the same walk to this one (DELETE: split it back out)
    POST   /api/v1/trails/{id}/photos    multipart photo + thumb (JPEG, made by the browser), taken, lat, lon, w, h
    GET    /api/v1/trails/{id}/photos/{photo}?thumb=   a photo
    DELETE /api/v1/trails/{id}/photos/{photo}
"""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from app.auth import require_user
from app.trails import service, tools

router = APIRouter(prefix="/api/v1/trails", tags=["trails"], dependencies=[Depends(require_user)])
MAX_EXPORT_BYTES = 8 * 1024 ** 3
WALK_ID = r"^w_[0-9a-f]{12}$"
PHOTO_ID = r"^p_[0-9a-f]{10}$"


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


# -- 12.5 ----------------------------------------------------------------------------------------------------------

def _run(fn, *args):  # noqa: ANN001, ANN202
    try:
        return fn(*args)
    except (KeyError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="No such walk.") from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/{walk_id}/gpx")
def gpx(walk_id: str = Path(pattern=WALK_ID), hide_home: bool = False) -> Response:
    body = _run(tools.gpx, walk_id, hide_home)
    return Response(body, media_type="application/gpx+xml", headers={"Content-Disposition": f'attachment; filename="{walk_id}.gpx"'})


class Trim(BaseModel):
    from_km: float = Field(ge=0, le=1000)
    to_km: float = Field(ge=0, le=1000)


@router.post("/{walk_id}/trim")
def trim(body: Trim, walk_id: str = Path(pattern=WALK_ID)) -> dict[str, Any]:
    if body.to_km <= body.from_km:
        raise HTTPException(status_code=422, detail="The end has to come after the start.")
    return _run(tools.trim, walk_id, body.from_km, body.to_km)


@router.delete("/{walk_id}/trim")
def untrim(walk_id: str = Path(pattern=WALK_ID)) -> dict[str, Any]:
    return _run(tools.untrim, walk_id)


class Join(BaseModel):
    other: str = Field(pattern=WALK_ID)


@router.post("/{walk_id}/join")
def join(body: Join, walk_id: str = Path(pattern=WALK_ID)) -> dict[str, Any]:
    return _run(tools.join, walk_id, body.other)


@router.delete("/{walk_id}/join")
def split(walk_id: str = Path(pattern=WALK_ID)) -> dict[str, Any]:
    return _run(tools.split, walk_id)


@router.post("/{walk_id}/photos")
async def add_photo(walk_id: str = Path(pattern=WALK_ID), photo: UploadFile = File(...), thumb: UploadFile = File(...),
                    taken: str | None = Form(None, max_length=40), lat: float | None = Form(None, ge=-90, le=90),
                    lon: float | None = Form(None, ge=-180, le=180), w: int | None = Form(None, ge=1, le=20000),
                    h: int | None = Form(None, ge=1, le=20000)) -> dict[str, Any]:
    full = await photo.read(tools.MAX_PHOTO_BYTES + 1)
    small = await thumb.read(tools.MAX_THUMB_BYTES + 1)
    return _run(tools.add_photo, walk_id, full, small, taken, lat, lon, w, h)


@router.get("/{walk_id}/photos/{photo_id}")
def get_photo(walk_id: str = Path(pattern=WALK_ID), photo_id: str = Path(pattern=PHOTO_ID), thumb: bool = False) -> FileResponse:
    path = _run(tools.photo_path, walk_id, photo_id, thumb)
    if not path.exists():
        raise HTTPException(status_code=404, detail="No such photo.")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=31536000, immutable"})


@router.delete("/{walk_id}/photos/{photo_id}")
def remove_photo(walk_id: str = Path(pattern=WALK_ID), photo_id: str = Path(pattern=PHOTO_ID)) -> dict[str, bool]:
    _run(tools.remove_photo, walk_id, photo_id)
    return {"ok": True}
