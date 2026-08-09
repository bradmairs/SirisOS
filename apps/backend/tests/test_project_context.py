import asyncio
from pathlib import Path

import jwt

from app.api import projects


def _token() -> str:
    return "Bearer " + jwt.encode(
        {"sub": projects.AUTH_USERNAME, "iss": "sirisos-api"},
        projects.JWT_SECRET,
        algorithm="HS256",
    )


def test_current_project_selection_and_auto_clear(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    monkeypatch.setattr(projects, "PROJECT_CONTEXT_PATH", tmp_path / "project-context.json")
    authorization = _token()

    created = asyncio.run(
        projects.create_project(
            projects.ProjectCreateRequest(name="Tank site drainage", kind="engineering"),
            authorization,
        )
    )

    selected = asyncio.run(
        projects.set_current_project(
            projects.CurrentProjectRequest(project_id=created.id),
            authorization,
        )
    )
    assert selected.project is not None
    assert selected.project.id == created.id
    assert selected.provenance == "manual"

    loaded = asyncio.run(projects.get_current_project(authorization))
    assert loaded.project is not None
    assert loaded.project.id == created.id

    asyncio.run(
        projects.update_project(
            created.id,
            projects.ProjectUpdateRequest(status="completed"),
            authorization,
        )
    )
    cleared = asyncio.run(projects.get_current_project(authorization))
    assert cleared.project is None


def test_completed_project_cannot_be_selected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    monkeypatch.setattr(projects, "PROJECT_CONTEXT_PATH", tmp_path / "project-context.json")
    authorization = _token()

    created = asyncio.run(
        projects.create_project(
            projects.ProjectCreateRequest(name="Finished", kind="personal"),
            authorization,
        )
    )
    asyncio.run(
        projects.update_project(
            created.id,
            projects.ProjectUpdateRequest(status="completed"),
            authorization,
        )
    )

    try:
        asyncio.run(
            projects.set_current_project(
                projects.CurrentProjectRequest(project_id=created.id),
                authorization,
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409
    else:
        raise AssertionError("Expected completed project selection to fail")
