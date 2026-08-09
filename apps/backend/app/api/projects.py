from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])
AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")
PROJECTS_PATH = Path(os.getenv("SIRISOS_PROJECTS_PATH", "/app/data/projects.json"))
PROJECT_CONTEXT_PATH = Path(
    os.getenv("SIRISOS_PROJECT_CONTEXT_PATH", "/app/data/project-context.json")
)

ProjectKind = Literal["engineering", "homelab", "travel", "fitness", "personal", "other"]
ProjectStatus = Literal["active", "paused", "completed", "archived"]


class ProjectRecord(BaseModel):
    id: str
    name: str
    description: str = ""
    kind: ProjectKind = "other"
    status: ProjectStatus = "active"
    tags: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    kind: ProjectKind = "other"
    tags: list[str] = Field(default_factory=list, max_length=30)


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    kind: ProjectKind | None = None
    status: ProjectStatus | None = None
    tags: list[str] | None = Field(default=None, max_length=30)


class ProjectListResponse(BaseModel):
    projects: list[ProjectRecord]


class CurrentProjectRequest(BaseModel):
    project_id: str | None = None


class CurrentProjectResponse(BaseModel):
    project: ProjectRecord | None = None
    selected_at: str | None = None
    provenance: str | None = None


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


def _normalise_tags(tags: list[str]) -> list[str]:
    values = {tag.strip().lstrip("#") for tag in tags if tag.strip().lstrip("#")}
    return sorted(values, key=str.lower)[:30]


def _load() -> list[ProjectRecord]:
    if not PROJECTS_PATH.exists():
        return []
    try:
        raw = json.loads(PROJECTS_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("project store root must be a list")
        return [ProjectRecord.model_validate(item) for item in raw]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="Project store is unavailable.") from exc


def _atomic_json_write(path: Path, payload: object, prefix: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=prefix,
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            temp_path = Path(handle.name)
        temp_path.replace(path)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Unable to persist project state.") from exc


def _save(projects: list[ProjectRecord]) -> None:
    _atomic_json_write(
        PROJECTS_PATH,
        [item.model_dump() for item in projects],
        ".projects-",
    )


def _find(projects: list[ProjectRecord], project_id: str) -> tuple[int, ProjectRecord]:
    for index, project in enumerate(projects):
        if project.id == project_id:
            return index, project
    raise HTTPException(status_code=404, detail="Project not found.")


def _load_current() -> dict[str, str | None]:
    if not PROJECT_CONTEXT_PATH.exists():
        return {"project_id": None, "selected_at": None, "provenance": None}
    try:
        raw = json.loads(PROJECT_CONTEXT_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("project context store root must be an object")
        return {
            "project_id": raw.get("project_id"),
            "selected_at": raw.get("selected_at"),
            "provenance": raw.get("provenance"),
        }
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="Project context is unavailable.") from exc


def _save_current(project_id: str | None) -> dict[str, str | None]:
    payload: dict[str, str | None] = {
        "project_id": project_id,
        "selected_at": datetime.now(timezone.utc).isoformat(),
        "provenance": "manual",
    }
    _atomic_json_write(PROJECT_CONTEXT_PATH, payload, ".project-context-")
    return payload


def _current_response(projects: list[ProjectRecord]) -> CurrentProjectResponse:
    selection = _load_current()
    project_id = selection.get("project_id")
    if not project_id:
        return CurrentProjectResponse(
            selected_at=selection.get("selected_at"),
            provenance=selection.get("provenance"),
        )
    project = next((item for item in projects if item.id == project_id), None)
    if project is None or project.status in {"completed", "archived"}:
        selection = _save_current(None)
        project = None
    return CurrentProjectResponse(
        project=project,
        selected_at=selection.get("selected_at"),
        provenance=selection.get("provenance"),
    )


@router.get("", response_model=ProjectListResponse)
async def list_projects(authorization: Annotated[str | None, Header()] = None) -> ProjectListResponse:
    _authenticate(authorization)
    projects = _load()
    projects.sort(key=lambda item: (item.status == "archived", item.name.lower()))
    return ProjectListResponse(projects=projects)


@router.post("", response_model=ProjectRecord, status_code=201)
async def create_project(
    request: ProjectCreateRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> ProjectRecord:
    _authenticate(authorization)
    projects = _load()
    now = datetime.now(timezone.utc).isoformat()
    project = ProjectRecord(
        id=str(uuid.uuid4()),
        name=request.name.strip(),
        description=request.description.strip(),
        kind=request.kind,
        tags=_normalise_tags(request.tags),
        created_at=now,
        updated_at=now,
    )
    projects.append(project)
    _save(projects)
    return project


@router.get("/current", response_model=CurrentProjectResponse)
async def get_current_project(
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentProjectResponse:
    _authenticate(authorization)
    return _current_response(_load())


@router.put("/current", response_model=CurrentProjectResponse)
async def set_current_project(
    request: CurrentProjectRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentProjectResponse:
    _authenticate(authorization)
    projects = _load()
    if request.project_id is None:
        selection = _save_current(None)
        return CurrentProjectResponse(
            selected_at=selection["selected_at"],
            provenance=selection["provenance"],
        )
    _, project = _find(projects, request.project_id)
    if project.status in {"completed", "archived"}:
        raise HTTPException(
            status_code=409,
            detail="Completed or archived projects cannot be the current project.",
        )
    selection = _save_current(project.id)
    return CurrentProjectResponse(
        project=project,
        selected_at=selection["selected_at"],
        provenance=selection["provenance"],
    )


@router.get("/{project_id}", response_model=ProjectRecord)
async def get_project(
    project_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> ProjectRecord:
    _authenticate(authorization)
    _, project = _find(_load(), project_id)
    return project


@router.patch("/{project_id}", response_model=ProjectRecord)
async def update_project(
    project_id: str,
    request: ProjectUpdateRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> ProjectRecord:
    _authenticate(authorization)
    projects = _load()
    index, existing = _find(projects, project_id)
    changes = request.model_dump(exclude_unset=True)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    if "description" in changes:
        changes["description"] = changes["description"].strip()
    if "tags" in changes:
        changes["tags"] = _normalise_tags(changes["tags"])
    changes["updated_at"] = datetime.now(timezone.utc).isoformat()
    updated = existing.model_copy(update=changes)
    projects[index] = updated
    _save(projects)
    if updated.status in {"completed", "archived"}:
        current = _load_current()
        if current.get("project_id") == updated.id:
            _save_current(None)
    return updated
