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


def test_project_create_update_and_list(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    authorization = _token()

    created = asyncio.run(
        projects.create_project(
            projects.ProjectCreateRequest(
                name="Penrith treatment plant",
                kind="engineering",
                tags=["stormwater", "#SydneyWater", "stormwater"],
            ),
            authorization,
        )
    )

    assert created.kind == "engineering"
    assert created.status == "active"
    assert created.tags == ["stormwater", "SydneyWater"]
    assert projects.PROJECTS_PATH.exists()

    updated = asyncio.run(
        projects.update_project(
            created.id,
            projects.ProjectUpdateRequest(status="paused", description="Civil design package"),
            authorization,
        )
    )
    assert updated.status == "paused"
    assert updated.description == "Civil design package"
    assert updated.updated_at >= created.updated_at

    listed = asyncio.run(projects.list_projects(authorization))
    assert [item.id for item in listed.projects] == [created.id]


def test_project_authentication_required(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    try:
        asyncio.run(projects.list_projects(None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 401
    else:
        raise AssertionError("Expected authentication failure")
