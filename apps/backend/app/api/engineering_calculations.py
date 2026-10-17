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

from app import main
from app.api import engineering_standards, projects
from app.engineering import calculators
from app.services.pdf_sheet import Sheet

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
    cited_standard_id: str | None = None
    cited_standard_label: str | None = None
    created_at: str


class CalculationCreateRequest(BaseModel):
    calculator_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    inputs: dict[str, float] = Field(default_factory=dict)
    results: list[CalculationResultItem] = Field(default_factory=list)
    notes: str = Field(default="", max_length=2000)
    cited_standard_id: str | None = None


def _standard_label(metadata: dict) -> str:
    normalised = engineering_standards._normalise_metadata(metadata)
    reference = str(normalised.get("reference") or "").strip()
    title = str(normalised.get("title") or "Engineering standard").strip()
    edition = str(normalised.get("edition") or "").strip()
    revision = int(normalised.get("revision") or 1)
    identity = reference or title
    parts = [identity]
    if edition:
        parts.append(edition)
    if revision > 1:
        parts.append(f"library rev. {revision}")
    return " · ".join(parts)


def _resolve_citation(record: CalculationRecord) -> CalculationRecord:
    if record.cited_standard_id is None:
        return record
    try:
        metadata = engineering_standards._load_metadata(record.cited_standard_id)
    except HTTPException:
        return record
    return record.model_copy(update={"cited_standard_label": _standard_label(metadata)})


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
    calculations = [_resolve_citation(item) for item in _load()]
    calculations.sort(key=lambda item: item.created_at, reverse=True)
    return CalculationListResponse(calculations=calculations)


@router.post("", response_model=CalculationRecord, status_code=201)
async def create_calculation(
    request: CalculationCreateRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> CalculationRecord:
    projects._authenticate(authorization)
    cited_standard_label = None
    if request.cited_standard_id is not None:
        metadata = engineering_standards._load_metadata(request.cited_standard_id)
        cited_standard_label = _standard_label(metadata)
    calculations = _load()
    record = CalculationRecord(
        id=str(uuid.uuid4()),
        calculator_id=request.calculator_id,
        title=request.title.strip(),
        inputs=request.inputs,
        results=request.results,
        notes=request.notes.strip(),
        cited_standard_id=request.cited_standard_id,
        cited_standard_label=cited_standard_label,
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
    return _resolve_citation(record)


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


def _number(value: float) -> str:
    return f"{value:g}"


def _linked_projects(calculation_id: str) -> list[str]:
    from app.api import project_relationships  # late: it imports this module's neighbours

    try:
        links = project_relationships._load()
        names = {p.id: p.name for p in projects._service().list_projects()}
    except Exception:  # noqa: BLE001 - the sheet still prints without a project
        return []
    return [names.get(link.project_id, link.project_id) for link in links if link.target_type == "calculation" and link.target_id == calculation_id]


def calculation_pdf(record: CalculationRecord, prepared_by: str = "") -> bytes:
    """The one-page calculation sheet for a design file."""
    calc = calculators.BY_ID.get(record.calculator_id)
    created = record.created_at[:10]
    sheet = Sheet()
    sheet.text("SirisOS · Engineering calculation", 8.5, bold=True, grey=True)
    sheet.space(10)
    sheet.text(record.title, 18, bold=True)
    sub = " · ".join(x for x in [calc.title if calc else record.calculator_id, calc.category if calc else "", created] if x)
    sheet.text(sub, 10, grey=True)
    linked = _linked_projects(record.id)
    if linked:
        sheet.text("Project: " + ", ".join(linked), 10, grey=True)
    if calc and calc.note:
        sheet.heading("Method")
        sheet.paragraph(calc.note, 10)
    sheet.heading("Inputs")
    fields = {f.key: f for f in calc.fields} if calc else {}
    for key, value in record.inputs.items():
        f = fields.get(key)
        sheet.row(f.label if f else key, f"{_number(value)} {f.unit}".strip() if f else _number(value))
    sheet.heading("Results")
    for item in record.results:
        sheet.row(item.label, item.value, bold_right=True)
    if record.notes:
        sheet.heading("Notes")
        sheet.paragraph(record.notes, 10)
    if record.cited_standard_label:
        sheet.heading("Reference")
        sheet.paragraph(record.cited_standard_label, 10)
    sheet.heading("Sign-off")
    sheet.row(f"Prepared by: {prepared_by}" if prepared_by else "Prepared by: ______________________", f"Date: {created}")
    sheet.row("Checked by: ______________________", "Date: ____________")
    sheet.footer([
        f"Generated by SirisOS {main.API_VERSION} on {datetime.now(timezone.utc).date().isoformat()} from saved calculation {record.id[:8]}.",
        "A screening calculation: check inputs, method and results against the governing standard before relying on it.",
    ])
    return sheet.pdf(record.title)


@router.get("/{calculation_id}/pdf", response_class=Response)
async def calculation_sheet(
    calculation_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    projects._authenticate(authorization)
    _, record = _find(_load(), calculation_id)
    record = _resolve_citation(record)
    name = "".join(ch if ch.isalnum() or ch in " -_" else "-" for ch in record.title).strip() or "calculation"
    return Response(
        calculation_pdf(record, prepared_by=projects.AUTH_USERNAME.capitalize()),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{name}.pdf"'},
    )
