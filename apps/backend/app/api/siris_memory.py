from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

import jwt
from fastapi import APIRouter, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/siris/memory", tags=["siris-memory"])
AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")
MEMORY_PATH = Path(os.getenv("SIRISOS_MEMORY_PATH", "/app/data/siris-memory.json"))
MAX_MEMORY_RECORDS = 1000

MemoryClass = Literal["fact", "preference", "episode", "decision", "observation", "conversation"]
MEMORY_CLASSES: tuple[MemoryClass, ...] = (
    "fact",
    "preference",
    "episode",
    "decision",
    "observation",
    "conversation",
)


class MemoryRecord(BaseModel):
    id: str
    memory_class: MemoryClass
    content: str
    source: str | None = None
    created_at: str


class MemoryCreateRequest(BaseModel):
    memory_class: MemoryClass
    content: str = Field(min_length=1, max_length=2000)
    source: str | None = Field(default=None, max_length=300)


class MemoryListResponse(BaseModel):
    memory: list[MemoryRecord]


def _authenticate(authorization: Annotated[str | None, Header()] = None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        payload = jwt.decode(
            authorization.removeprefix("Bearer ").strip(),
            JWT_SECRET,
            algorithms=["HS256"],
            issuer="sirisos-api",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session.") from exc
    if payload.get("sub") != AUTH_USERNAME:
        raise HTTPException(status_code=401, detail="Invalid session user.")


def _load() -> list[MemoryRecord]:
    if not MEMORY_PATH.exists():
        return []
    try:
        raw = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("Siris memory store root must be a list")
        return [MemoryRecord.model_validate(item) for item in raw]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="Siris memory store is unavailable.") from exc


def _save(records: list[MemoryRecord]) -> None:
    try:
        MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps([item.model_dump() for item in records], indent=2, ensure_ascii=False) + "\n"
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=MEMORY_PATH.parent,
            prefix=".siris-memory-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            temp_path = Path(handle.name)
        temp_path.replace(MEMORY_PATH)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Unable to persist Siris memory.") from exc


@router.get("", response_model=MemoryListResponse)
async def list_memory(
    authorization: Annotated[str | None, Header()] = None,
    memory_class: Annotated[MemoryClass | None, Query()] = None,
) -> MemoryListResponse:
    _authenticate(authorization)
    records = _load()
    if memory_class is not None:
        records = [item for item in records if item.memory_class == memory_class]
    records.sort(key=lambda item: item.created_at, reverse=True)
    return MemoryListResponse(memory=records)


@router.post("", response_model=MemoryRecord, status_code=201)
async def create_memory(
    request: MemoryCreateRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> MemoryRecord:
    _authenticate(authorization)
    records = _load()
    record = MemoryRecord(
        id=str(uuid.uuid4()),
        memory_class=request.memory_class,
        content=request.content.strip(),
        source=(request.source.strip() or None) if request.source else None,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    records.append(record)
    _save(records[-MAX_MEMORY_RECORDS:])
    return record


@router.delete("/{record_id}", status_code=204, response_class=Response)
async def delete_memory(
    record_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    _authenticate(authorization)
    records = _load()
    remaining = [item for item in records if item.id != record_id]
    if len(remaining) == len(records):
        raise HTTPException(status_code=404, detail="Memory record not found.")
    _save(remaining)
    return Response(status_code=204)
