from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import jwt
from fastapi import APIRouter, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field

from app.services.siris_memory_service import (
    MemoryClass,
    MemoryNotFoundError,
    MemoryStoreUnavailableError,
    SirisMemoryService,
)

router = APIRouter(prefix="/api/v1/siris/memory", tags=["siris-memory"])
AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")
MEMORY_PATH = Path(os.getenv("SIRISOS_MEMORY_PATH", "/app/data/siris-memory.json"))


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


class MemorySuggestRequest(BaseModel):
    user_message: str = Field(min_length=1, max_length=4000)
    assistant_message: str = Field(min_length=1, max_length=4000)


class MemorySuggestionResponse(BaseModel):
    memory_class: MemoryClass
    content: str


class MemorySuggestResponse(BaseModel):
    suggestions: list[MemorySuggestionResponse]


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


def _service() -> SirisMemoryService:
    # Constructed fresh per request, reading the current module-level
    # MEMORY_PATH global, so tests that monkeypatch it per-test keep
    # working exactly as before this delegated to SirisMemoryService (the
    # same lesson ADR 094/098 already learned the hard way).
    return SirisMemoryService(memory_path=MEMORY_PATH)


def _record(memory) -> MemoryRecord:
    return MemoryRecord(**memory.__dict__)


@router.get("", response_model=MemoryListResponse)
async def list_memory(
    authorization: Annotated[str | None, Header()] = None,
    memory_class: Annotated[MemoryClass | None, Query()] = None,
) -> MemoryListResponse:
    _authenticate(authorization)
    try:
        records = _service().list_memory(memory_class=memory_class)
    except MemoryStoreUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return MemoryListResponse(memory=[_record(item) for item in records])


@router.post("", response_model=MemoryRecord, status_code=201)
async def create_memory(
    request: MemoryCreateRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> MemoryRecord:
    _authenticate(authorization)
    try:
        record = _service().create_memory(
            memory_class=request.memory_class, content=request.content, source=request.source
        )
    except MemoryStoreUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _record(record)


@router.post("/suggest", response_model=MemorySuggestResponse)
async def suggest_memory(
    request: MemorySuggestRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> MemorySuggestResponse:
    """Best-effort: extracts candidate memories from one real chat exchange for the
    user to review, never auto-saves. Fails open (empty suggestions) on any error --
    a suggestion failure must never surface as a chat error to the user."""
    _authenticate(authorization)
    suggestions = await _service().suggest(
        user_message=request.user_message, assistant_message=request.assistant_message
    )
    return MemorySuggestResponse(
        suggestions=[
            MemorySuggestionResponse(memory_class=item.memory_class, content=item.content)
            for item in suggestions
        ]
    )


@router.delete("/{record_id}", status_code=204, response_class=Response)
async def delete_memory(
    record_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    _authenticate(authorization)
    try:
        _service().delete_memory(record_id)
    except MemoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Memory record not found.") from exc
    except MemoryStoreUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(status_code=204)
