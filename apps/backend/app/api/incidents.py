import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

# The Incident Engine itself (correlation/grouping of policy outcomes into
# incidents) is entirely client-side (apps/mobile's IncidentEngine) -- there
# is no backend representation of what an incident *is*. This module only
# tracks the human-facing lifecycle (acknowledge/assign/resolve) for whatever
# incident id the client is currently showing, keyed by that already-stable
# id (e.g. "incident.power", "incident.compute"). It never discovers
# incidents on its own; a record is created the first time a client PATCHes
# one, matching Recommendations' first-detection-creates-a-record shape
# (ADR 064) as closely as the different discovery model allows.
router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])

AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")
INCIDENT_LIFECYCLE_PATH = Path(os.getenv("SIRISOS_INCIDENT_LIFECYCLE_PATH", "/app/data/incident_lifecycle.json"))
MAX_INCIDENT_LIFECYCLE_RECORDS = 500

IncidentLifecycleStatus = Literal["open", "acknowledged", "resolved"]


class IncidentLifecycleRecord(BaseModel):
    id: str
    status: IncidentLifecycleStatus
    assigned_to: str | None = None
    notes: str | None = None
    created_at: str
    updated_at: str
    acknowledged_at: str | None = None
    resolved_at: str | None = None


class IncidentLifecycleUpdate(BaseModel):
    status: IncidentLifecycleStatus
    assigned_to: str | None = None
    notes: str | None = None


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


def _load() -> list[IncidentLifecycleRecord]:
    if not INCIDENT_LIFECYCLE_PATH.exists():
        return []
    try:
        raw = json.loads(INCIDENT_LIFECYCLE_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("Incident lifecycle store root must be a list")
        return [IncidentLifecycleRecord.model_validate(item) for item in raw]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="Incident lifecycle store is unavailable.") from exc


def _save(records: list[IncidentLifecycleRecord]) -> None:
    try:
        INCIDENT_LIFECYCLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps([item.model_dump() for item in records], indent=2, ensure_ascii=False) + "\n"
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=INCIDENT_LIFECYCLE_PATH.parent,
            prefix=".incident-lifecycle-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            temp_path = Path(handle.name)
        temp_path.replace(INCIDENT_LIFECYCLE_PATH)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Unable to persist incident lifecycle.") from exc


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


@router.get("", response_model=list[IncidentLifecycleRecord])
async def list_incident_lifecycle(
    authorization: Annotated[str | None, Header()] = None,
) -> list[IncidentLifecycleRecord]:
    _authenticate(authorization)
    return _load()


@router.patch("/{incident_id}", response_model=IncidentLifecycleRecord)
async def update_incident_lifecycle(
    incident_id: str,
    request: IncidentLifecycleUpdate,
    authorization: Annotated[str | None, Header()] = None,
) -> IncidentLifecycleRecord:
    _authenticate(authorization)
    records = _load()
    now = _now_iso()
    existing = next((item for item in records if item.id == incident_id), None)

    # acknowledged_at is stamped once and kept; resolved_at refreshes on every
    # resolution and is backfilled with an implicit acknowledgement if the
    # incident jumped straight from open to resolved. Reopening clears both,
    # a deliberate fresh start rather than preserving stale timestamps from a
    # prior occurrence of the same incident id.
    acknowledged_at = existing.acknowledged_at if existing else None
    resolved_at = existing.resolved_at if existing else None
    if request.status == "acknowledged" and acknowledged_at is None:
        acknowledged_at = now
    elif request.status == "resolved":
        resolved_at = now
        if acknowledged_at is None:
            acknowledged_at = now
    elif request.status == "open":
        acknowledged_at = None
        resolved_at = None

    record = IncidentLifecycleRecord(
        id=incident_id,
        status=request.status,
        assigned_to=request.assigned_to,
        notes=request.notes,
        created_at=existing.created_at if existing else now,
        updated_at=now,
        acknowledged_at=acknowledged_at,
        resolved_at=resolved_at,
    )

    if existing is None:
        records.append(record)
    else:
        records[records.index(existing)] = record

    if len(records) > MAX_INCIDENT_LIFECYCLE_RECORDS:
        records = records[-MAX_INCIDENT_LIFECYCLE_RECORDS:]

    _save(records)
    return record
