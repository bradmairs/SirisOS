from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

ProjectKind = Literal["engineering", "homelab", "travel", "fitness", "personal", "other"]
ProjectStatus = Literal["active", "paused", "completed", "archived"]


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    description: str
    kind: ProjectKind
    status: ProjectStatus
    tags: list[str]
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class CurrentProjectSelection:
    project: Project | None
    selected_at: str | None
    provenance: str | None


class ProjectNotFoundError(Exception):
    pass


class ProjectStoreUnavailableError(Exception):
    pass


def _default_projects_path() -> Path:
    return Path(os.getenv("SIRISOS_PROJECTS_PATH", "/app/data/projects.json"))


def _default_project_context_path() -> Path:
    return Path(os.getenv("SIRISOS_PROJECT_CONTEXT_PATH", "/app/data/project-context.json"))


def normalise_tags(tags: list[str]) -> list[str]:
    values = {tag.strip().lstrip("#") for tag in tags if tag.strip().lstrip("#")}
    return sorted(values, key=str.lower)[:30]


def _atomic_json_write(path: Path, payload: object, prefix: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=prefix, suffix=".tmp", delete=False
        ) as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            temp_path = Path(handle.name)
        temp_path.replace(path)
    except OSError as exc:
        raise ProjectStoreUnavailableError("Unable to persist project state.") from exc


class ProjectService:
    """Atomic-JSON-file-backed project store -- the same PROJECTS_PATH/
    PROJECT_CONTEXT_PATH files app/api/projects.py has always used. Callers
    that only need read access (SirisAgent) can use list_projects() and
    current_project() directly; app/api/projects.py itself delegates every
    route here so there's one implementation, not two."""

    def __init__(self, projects_path: Path | None = None, project_context_path: Path | None = None) -> None:
        self._projects_path = projects_path or _default_projects_path()
        self._project_context_path = project_context_path or _default_project_context_path()

    def list_projects(self) -> list[Project]:
        projects = self._load()
        projects.sort(key=lambda item: (item.status == "archived", item.name.lower()))
        return projects

    def get_project(self, project_id: str) -> Project:
        _, project = self._find(self._load(), project_id)
        return project

    def create_project(
        self, *, name: str, description: str = "", kind: ProjectKind = "other", tags: list[str] | None = None
    ) -> Project:
        projects = self._load()
        now = datetime.now(timezone.utc).isoformat()
        project = Project(
            id=str(uuid.uuid4()),
            name=name.strip(),
            description=description.strip(),
            kind=kind,
            status="active",
            tags=normalise_tags(tags or []),
            created_at=now,
            updated_at=now,
        )
        projects.append(project)
        self._save(projects)
        return project

    def update_project(self, project_id: str, changes: dict[str, Any]) -> Project:
        projects = self._load()
        index, existing = self._find(projects, project_id)
        resolved = dict(changes)
        if "name" in resolved and resolved["name"] is not None:
            resolved["name"] = resolved["name"].strip()
        if "description" in resolved and resolved["description"] is not None:
            resolved["description"] = resolved["description"].strip()
        if "tags" in resolved and resolved["tags"] is not None:
            resolved["tags"] = normalise_tags(resolved["tags"])
        resolved = {key: value for key, value in resolved.items() if value is not None}
        resolved["updated_at"] = datetime.now(timezone.utc).isoformat()
        updated = Project(**{**existing.__dict__, **resolved})
        projects[index] = updated
        self._save(projects)
        if updated.status in {"completed", "archived"}:
            current = self._load_current()
            if current.get("project_id") == updated.id:
                self._save_current(None)
        return updated

    def current_project(self) -> CurrentProjectSelection:
        return self._current_response(self._load())

    def set_current_project(self, project_id: str | None) -> CurrentProjectSelection:
        projects = self._load()
        if project_id is None:
            selection = self._save_current(None)
            return CurrentProjectSelection(
                project=None, selected_at=selection["selected_at"], provenance=selection["provenance"]
            )
        _, project = self._find(projects, project_id)
        if project.status in {"completed", "archived"}:
            raise ValueError("Completed or archived projects cannot be the current project.")
        selection = self._save_current(project.id)
        return CurrentProjectSelection(
            project=project, selected_at=selection["selected_at"], provenance=selection["provenance"]
        )

    def _load(self) -> list[Project]:
        if not self._projects_path.exists():
            return []
        try:
            raw = json.loads(self._projects_path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raise ValueError("project store root must be a list")
            return [Project(**item) for item in raw]
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ProjectStoreUnavailableError("Project store is unavailable.") from exc

    def _save(self, projects: list[Project]) -> None:
        _atomic_json_write(self._projects_path, [item.__dict__ for item in projects], ".projects-")

    @staticmethod
    def _find(projects: list[Project], project_id: str) -> tuple[int, Project]:
        for index, project in enumerate(projects):
            if project.id == project_id:
                return index, project
        raise ProjectNotFoundError(f"Project '{project_id}' not found.")

    def _load_current(self) -> dict[str, str | None]:
        if not self._project_context_path.exists():
            return {"project_id": None, "selected_at": None, "provenance": None}
        try:
            raw = json.loads(self._project_context_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("project context store root must be an object")
            return {
                "project_id": raw.get("project_id"),
                "selected_at": raw.get("selected_at"),
                "provenance": raw.get("provenance"),
            }
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ProjectStoreUnavailableError("Project context is unavailable.") from exc

    def _save_current(self, project_id: str | None) -> dict[str, str | None]:
        payload: dict[str, str | None] = {
            "project_id": project_id,
            "selected_at": datetime.now(timezone.utc).isoformat(),
            "provenance": "manual",
        }
        _atomic_json_write(self._project_context_path, payload, ".project-context-")
        return payload

    def _current_response(self, projects: list[Project]) -> CurrentProjectSelection:
        selection = self._load_current()
        project_id = selection.get("project_id")
        if not project_id:
            return CurrentProjectSelection(
                project=None, selected_at=selection.get("selected_at"), provenance=selection.get("provenance")
            )
        project = next((item for item in projects if item.id == project_id), None)
        if project is None or project.status in {"completed", "archived"}:
            selection = self._save_current(None)
            project = None
        return CurrentProjectSelection(
            project=project, selected_at=selection.get("selected_at"), provenance=selection.get("provenance")
        )
