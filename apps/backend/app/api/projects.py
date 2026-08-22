from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.services.project_service import (
    ProjectKind,
    ProjectNotFoundError,
    ProjectService,
    ProjectStatus,
    ProjectStoreUnavailableError,
)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])
AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")
PROJECTS_PATH = Path(os.getenv("SIRISOS_PROJECTS_PATH", "/app/data/projects.json"))
PROJECT_CONTEXT_PATH = Path(
    os.getenv("SIRISOS_PROJECT_CONTEXT_PATH", "/app/data/project-context.json")
)


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


def _service() -> ProjectService:
    # Constructed fresh per request (reading the current module-level path
    # globals) rather than a singleton, so tests that monkeypatch
    # PROJECTS_PATH/PROJECT_CONTEXT_PATH per-test keep working exactly as
    # before this delegated to ProjectService.
    return ProjectService(projects_path=PROJECTS_PATH, project_context_path=PROJECT_CONTEXT_PATH)


def _record(project) -> ProjectRecord:
    return ProjectRecord(**project.__dict__)


def _current_response(selection) -> CurrentProjectResponse:
    return CurrentProjectResponse(
        project=_record(selection.project) if selection.project else None,
        selected_at=selection.selected_at,
        provenance=selection.provenance,
    )


@router.get("", response_model=ProjectListResponse)
async def list_projects(authorization: Annotated[str | None, Header()] = None) -> ProjectListResponse:
    _authenticate(authorization)
    try:
        projects = _service().list_projects()
    except ProjectStoreUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ProjectListResponse(projects=[_record(item) for item in projects])


@router.post("", response_model=ProjectRecord, status_code=201)
async def create_project(
    request: ProjectCreateRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> ProjectRecord:
    _authenticate(authorization)
    try:
        project = _service().create_project(
            name=request.name, description=request.description, kind=request.kind, tags=request.tags
        )
    except ProjectStoreUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _record(project)


@router.get("/current", response_model=CurrentProjectResponse)
async def get_current_project(
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentProjectResponse:
    _authenticate(authorization)
    try:
        selection = _service().current_project()
    except ProjectStoreUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _current_response(selection)


@router.put("/current", response_model=CurrentProjectResponse)
async def set_current_project(
    request: CurrentProjectRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentProjectResponse:
    _authenticate(authorization)
    try:
        selection = _service().set_current_project(request.project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProjectStoreUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _current_response(selection)


@router.get("/{project_id}", response_model=ProjectRecord)
async def get_project(
    project_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> ProjectRecord:
    _authenticate(authorization)
    try:
        project = _service().get_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except ProjectStoreUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _record(project)


@router.patch("/{project_id}", response_model=ProjectRecord)
async def update_project(
    project_id: str,
    request: ProjectUpdateRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> ProjectRecord:
    _authenticate(authorization)
    try:
        project = _service().update_project(project_id, request.model_dump(exclude_unset=True))
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except ProjectStoreUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _record(project)
