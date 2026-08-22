from pathlib import Path

import pytest

from app.services.project_service import (
    ProjectNotFoundError,
    ProjectService,
    ProjectStoreUnavailableError,
)


def _service(tmp_path: Path) -> ProjectService:
    return ProjectService(
        projects_path=tmp_path / "projects.json",
        project_context_path=tmp_path / "project-context.json",
    )


def test_create_list_and_get_project(tmp_path: Path) -> None:
    service = _service(tmp_path)

    created = service.create_project(
        name="Penrith treatment plant", kind="engineering", tags=["stormwater", "#SydneyWater", "stormwater"]
    )

    assert created.status == "active"
    assert created.tags == ["stormwater", "SydneyWater"]
    assert (tmp_path / "projects.json").exists()

    listed = service.list_projects()
    assert [item.id for item in listed] == [created.id]

    fetched = service.get_project(created.id)
    assert fetched.name == "Penrith treatment plant"


def test_get_project_raises_not_found(tmp_path: Path) -> None:
    service = _service(tmp_path)

    with pytest.raises(ProjectNotFoundError):
        service.get_project("does-not-exist")


def test_update_project_applies_only_provided_fields(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Alpha")

    updated = service.update_project(created.id, {"status": "paused", "description": "Civil design package"})

    assert updated.status == "paused"
    assert updated.description == "Civil design package"
    assert updated.name == "Alpha"  # untouched


def test_archived_projects_sort_last(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.create_project(name="Zebra")
    archived = service.create_project(name="Alpha")
    service.update_project(archived.id, {"status": "archived"})

    listed = service.list_projects()

    assert [item.name for item in listed] == ["Zebra", "Alpha"]


def test_current_project_defaults_to_none(tmp_path: Path) -> None:
    service = _service(tmp_path)

    selection = service.current_project()

    assert selection.project is None
    assert selection.selected_at is None


def test_set_and_get_current_project(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Alpha")

    service.set_current_project(created.id)
    selection = service.current_project()

    assert selection.project is not None
    assert selection.project.id == created.id
    assert selection.provenance == "manual"


def test_completed_project_cannot_become_current(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Alpha")
    service.update_project(created.id, {"status": "completed"})

    with pytest.raises(ValueError):
        service.set_current_project(created.id)


def test_current_project_clears_itself_once_archived(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.create_project(name="Alpha")
    service.set_current_project(created.id)

    service.update_project(created.id, {"status": "archived"})

    assert service.current_project().project is None


def test_corrupted_store_raises_unavailable(tmp_path: Path) -> None:
    path = tmp_path / "projects.json"
    path.write_text("not json", encoding="utf-8")
    service = _service(tmp_path)

    with pytest.raises(ProjectStoreUnavailableError):
        service.list_projects()


def test_no_store_file_returns_empty_list(tmp_path: Path) -> None:
    service = _service(tmp_path)

    assert service.list_projects() == []
