from __future__ import annotations

import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, Field

from app.api import engineering_standards, knowledge, projects

router = APIRouter(prefix="/api/v1/projects", tags=["project-relationships"])

RelationshipKind = Literal["contains", "references"]
TargetType = Literal["knowledge_note", "engineering_standard"]
RelationshipProvenance = Literal["manual"]
MAX_GRAPH_RELATIONSHIPS = 100


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


class ProjectGraphNode(BaseModel):
    id: str
    label: str
    node_type: Literal["project", "knowledge_note", "engineering_standard"]
    detail: str = ""
    center: bool = False


class ProjectGraphEdge(BaseModel):
    source: str
    target: str
    kind: RelationshipKind
    label: str
    provenance: RelationshipProvenance


class ProjectGraphResponse(BaseModel):
    project_id: str
    nodes: list[ProjectGraphNode]
    edges: list[ProjectGraphEdge]


def _relationships_path() -> Path:
    return projects.PROJECTS_PATH.with_name("project_relationships.json")


def _load() -> list[ProjectRelationshipRecord]:
    path = _relationships_path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("relationship store root must be a list")
        return [ProjectRelationshipRecord.model_validate(item) for item in raw]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="Project relationship store is unavailable.") from exc


def _save(relationships: list[ProjectRelationshipRecord]) -> None:
    path = _relationships_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        [item.model_dump() for item in relationships],
        indent=2,
        ensure_ascii=False,
    ) + "\n"
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".project-relationships-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            temp_path = Path(handle.name)
        temp_path.replace(path)
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


def _canonical_standard_target(target_id: str) -> tuple[str, str]:
    document_id = target_id.strip()
    metadata = engineering_standards._load_metadata(document_id)
    return document_id, _standard_label(metadata)


def _canonical_target(target_type: TargetType, target_id: str) -> tuple[str, str]:
    if target_type == "knowledge_note":
        return _canonical_knowledge_target(target_id)
    return _canonical_standard_target(target_id)


def _refresh_target_label(item: ProjectRelationshipRecord) -> ProjectRelationshipRecord:
    try:
        target_id, label = _canonical_target(item.target_type, item.target_id)
    except HTTPException:
        return item
    return item.model_copy(update={"target_id": target_id, "target_label": label})


def _project_relationships(project_id: str) -> list[ProjectRelationshipRecord]:
    values = [
        _refresh_target_label(item)
        for item in _load()
        if item.project_id == project_id
    ]
    values.sort(key=lambda item: (item.target_type, item.target_label.lower(), item.created_at))
    return values


@router.get("/{project_id}/relationships", response_model=ProjectRelationshipListResponse)
async def list_project_relationships(
    project_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> ProjectRelationshipListResponse:
    projects._authenticate(authorization)
    _require_project(project_id)
    return ProjectRelationshipListResponse(
        project_id=project_id,
        relationships=_project_relationships(project_id),
    )


@router.get("/{project_id}/graph", response_model=ProjectGraphResponse)
async def get_project_graph(
    project_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> ProjectGraphResponse:
    projects._authenticate(authorization)
    project = _require_project(project_id)
    relationships = _project_relationships(project_id)[:MAX_GRAPH_RELATIONSHIPS]

    project_node_id = f"project:{project.id}"
    nodes = [
        ProjectGraphNode(
            id=project_node_id,
            label=project.name,
            node_type="project",
            detail=f"{project.kind} · {project.status}",
            center=True,
        )
    ]
    edges: list[ProjectGraphEdge] = []
    seen_targets: set[str] = set()

    for relationship in relationships:
        target_node_id = f"{relationship.target_type}:{relationship.target_id}"
        if target_node_id not in seen_targets:
            seen_targets.add(target_node_id)
            nodes.append(
                ProjectGraphNode(
                    id=target_node_id,
                    label=relationship.target_label,
                    node_type=relationship.target_type,
                    detail=relationship.target_id,
                )
            )
        edges.append(
            ProjectGraphEdge(
                source=project_node_id,
                target=target_node_id,
                kind=relationship.kind,
                label="Part of project" if relationship.kind == "contains" else "Reference",
                provenance=relationship.provenance,
            )
        )

    return ProjectGraphResponse(project_id=project.id, nodes=nodes, edges=edges)


@router.post("/{project_id}/relationships", response_model=ProjectRelationshipRecord, status_code=201)
async def create_project_relationship(
    project_id: str,
    request: ProjectRelationshipCreateRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> ProjectRelationshipRecord:
    projects._authenticate(authorization)
    _require_project(project_id)

    if request.target_type == "engineering_standard" and request.kind != "references":
        raise HTTPException(
            status_code=422,
            detail="Engineering standards can only be attached as references.",
        )

    target_id, target_label = _canonical_target(request.target_type, request.target_id)
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


@router.delete(
    "/{project_id}/relationships/{relationship_id}",
    status_code=204,
    response_class=Response,
)
async def delete_project_relationship(
    project_id: str,
    relationship_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
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
    return Response(status_code=204)
