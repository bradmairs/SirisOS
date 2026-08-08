from __future__ import annotations

import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.api import knowledge, projects

router = APIRouter(prefix="/api/v1/projects", tags=["project-relationships"])
RELATIONSHIPS_PATH = projects.PROJECTS_PATH.with_name("project_relationships.json")

RelationshipKind = Literal["contains", "references"]
TargetType = Literal["knowledge_note"]
RelationshipProvenance = Literal["manual"]


class ProjectRelationshipRecord(BaseModel):
    id: str
    project_id: str
    target_type: TargetType
    target_id: str
    target_label: str
    kind: RelationshipKind
    provenance: RelationshipProvenance = "manual"
    created_at: str


class ProjectRelationshipCreateRequest(BaseModel):
    target_type: TargetType = "knowledge_note"
    target_id: str = Field(min_length=1, max_length=1000)
    kind: RelationshipKind = "contains"


class ProjectRelationshipListResponse(BaseModel):
    project_id: str
    relationships: list[ProjectRelationshipRecord]


def _load() -> list[ProjectRelationshipRecord]:
    if not RELATIONSHIPS_PATH.exists():
        return []
    try:
        raw = json.loads(RELATIONSHIPS_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("relationship store root must be a list")
        return [ProjectRelationshipRecord.model_validate(item) for item in raw]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="Project relationship store is unavailable.") from exc


def _save(relationships: list[ProjectRelationshipRecord]) -> None:
    RELATIONSHIPS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        [item.model_dump() for item in relationships],
        indent=2,
        ensure_ascii=False,
    ) + "\n"
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=RELATIONSHIPS_PATH.parent,
            prefix=".project-relationships-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            temp_path = Path(handle.name)
        temp_path.replace(RELATIONSHIPS_PATH)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Unable to persist project relationships.") from exc


def _require_project(project_id: str) -> projects.ProjectRecord:
    _, project = projects._find(projects._load(), project_id)
    return project


def _canonical_knowledge_target(target_id: str) -> tuple[str, str]:
    path = knowledge._safe_note_path(target_id.strip())
    text = knowledge._read_text(path)
    summary = knowledge._summary(path, text)
    return summary.path, summary.title


def _refresh_target_label(item: ProjectRelationshipRecord) -> ProjectRelationshipRecord:
    try:
        target_id, label = _canonical_knowledge_target(item.target_id)
    except HTTPException:
        return item
    return item.model_copy(update={"target_id": target_id, "target_label": label})


@router.get("/{project_id}/relationships", response_model=ProjectRelationshipListResponse)
async def list_project_relationships(
    project_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> ProjectRelationshipListResponse:
    projects._authenticate(authorization)
    _require_project(project_id)
    values = [
        _refresh_target_label(item)
        for item in _load()
        if item.project_id == project_id
    ]
    values.sort(key=lambda item: (item.target_type, item.target_label.lower(), item.created_at))
    return ProjectRelationshipListResponse(project_id=project_id, relationships=values)


@router.post("/{project_id}/relationships", response_model=ProjectRelationshipRecord, status_code=201)
async def create_project_relationship(
    project_id: str,
    request: ProjectRelationshipCreateRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> ProjectRelationshipRecord:
    projects._authenticate(authorization)
    _require_project(project_id)

    target_id, target_label = _canonical_knowledge_target(request.target_id)
    relationships = _load()
    duplicate = next(
        (
            item
            for item in relationships
            if item.project_id == project_id
            and item.target_type == request.target_type
            and item.target_id == target_id
            and item.kind == request.kind
        ),
        None,
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Project relationship already exists.")

    item = ProjectRelationshipRecord(
        id=str(uuid.uuid4()),
        project_id=project_id,
        target_type=request.target_type,
        target_id=target_id,
        target_label=target_label,
        kind=request.kind,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    relationships.append(item)
    _save(relationships)
    return item


@router.delete("/{project_id}/relationships/{relationship_id}", status_code=204)
async def delete_project_relationship(
    project_id: str,
    relationship_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    projects._authenticate(authorization)
    _require_project(project_id)
    relationships = _load()
    remaining = [
        item
        for item in relationships
        if not (item.project_id == project_id and item.id == relationship_id)
    ]
    if len(remaining) == len(relationships):
        raise HTTPException(status_code=404, detail="Project relationship not found.")
    _save(remaining)
