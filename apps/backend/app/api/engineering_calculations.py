from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, Field

from app.api import projects

router = APIRouter(prefix="/api/v1/engineering/calculations", tags=["engineering"])

CALCULATIONS_PATH = Path(
    os.getenv("SIRISOS_ENGINEERING_CALCULATIONS_PATH", "/app/data/engineering-calculations.json")
)


class CalculationResultItem(BaseModel):
    label: str
    value: str


class CalculationRecord(BaseModel):
    id: str
    calculator_id: str
    title: str
    inputs: dict[str, float]
    results: list[CalculationResultItem]
    notes: str = ""
    created_at: str


class CalculationCreateRequest(BaseModel):
    calculator_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    inputs: dict[str, float] = Field(default_factory=dict)
    results: list[CalculationResultItem] = Field(default_factory=list)
    notes: str = Field(default="", max_length=2000)


class CalculationListResponse(BaseModel):
    calculations: list[CalculationRecord]


def _load() -> list[CalculationRecord]:
    if not CALCULATIONS_PATH.exists():
        return []
    try:
        raw = json.loads(CALCULATIONS_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("calculation store root must be a list")
        return [CalculationRecord.model_validate(item) for item in raw]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="Calculation store is unavailable.") from exc


def _save(calculations: list[CalculationRecord]) -> None:
    CALCULATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(
            [item.model_dump() for item in calculations],
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=CALCULATIONS_PATH.parent,
            prefix=".engineering-calculations-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            temp_path = Path(handle.name)
        temp_path.replace(CALCULATIONS_PATH)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Unable to persist calculation.") from exc


def _find(calculations: list[CalculationRecord], calculation_id: str) -> tuple[int, CalculationRecord]:
    for index, item in enumerate(calculations):
        if item.id == calculation_id:
            return index, item
    raise HTTPException(status_code=404, detail="Calculation not found.")


@router.get("", response_model=CalculationListResponse)
async def list_calculations(authorization: Annotated[str | None, Header()] = None) -> CalculationListResponse:
    projects._authenticate(authorization)
    calculations = _load()
    calculations.sort(key=lambda item: item.created_at, reverse=True)
    return CalculationListResponse(calculations=calculations)


@router.post("", response_model=CalculationRecord, status_code=201)
async def create_calculation(
    request: CalculationCreateRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> CalculationRecord:
    projects._authenticate(authorization)
    calculations = _load()
    record = CalculationRecord(
        id=str(uuid.uuid4()),
        calculator_id=request.calculator_id,
        title=request.title.strip(),
        inputs=request.inputs,
        results=request.results,
        notes=request.notes.strip(),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    calculations.append(record)
    _save(calculations)
    return record


@router.get("/{calculation_id}", response_model=CalculationRecord)
async def get_calculation(
    calculation_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> CalculationRecord:
    projects._authenticate(authorization)
    _, record = _find(_load(), calculation_id)
    return record


@router.delete("/{calculation_id}", status_code=204, response_class=Response)
async def delete_calculation(
    calculation_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    projects._authenticate(authorization)
    calculations = _load()
    remaining = [item for item in calculations if item.id != calculation_id]
    if len(remaining) == len(calculations):
        raise HTTPException(status_code=404, detail="Calculation not found.")
    _save(remaining)
    return Response(status_code=204)
