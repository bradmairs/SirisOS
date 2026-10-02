import asyncio
import json
from pathlib import Path

import jwt

from app.api import engineering_calculations, engineering_standards, project_relationships, projects


def _token() -> str:
    return "Bearer " + jwt.encode(
        {"sub": projects.AUTH_USERNAME, "iss": "sirisos-api"},
        projects.JWT_SECRET,
        algorithm="HS256",
    )


def _create_project(authorization: str) -> projects.ProjectRecord:
    return asyncio.run(
        projects.create_project(
            projects.ProjectCreateRequest(name="Tank site drainage", kind="engineering"),
            authorization,
        )
    )


def _create_standard(library_root: Path, document_id: str = "std-1") -> None:
    directory = library_root / document_id
    directory.mkdir(parents=True)
    (directory / "metadata.json").write_text(
        json.dumps(
            {
                "id": document_id,
                "title": "Concrete structures",
                "authority": "Standards Australia",
                "reference": "AS 3600",
                "edition": "2018",
                "filename": "as3600.pdf",
                "uploaded_at": "2026-01-01T00:00:00+00:00",
                "pages": 10,
                "indexed": True,
            }
        ),
        encoding="utf-8",
    )


def _create_calculation(calculations_path: Path) -> engineering_calculations.CalculationRecord:
    calculations_path.parent.mkdir(parents=True, exist_ok=True)
    record = engineering_calculations.CalculationRecord(
        id="calc-1",
        calculator_id="minorLoss",
        title="Pump station discharge manifold",
        inputs={"flowM3s": 0.05, "diameterM": 0.20, "sumKValues": 1.5},
        results=[
            engineering_calculations.CalculationResultItem(label="Minor headloss", value="0.194 m"),
        ],
        notes="",
        created_at="2026-01-01T00:00:00+00:00",
    )
    calculations_path.write_text(
        json.dumps([record.model_dump()], indent=2),
        encoding="utf-8",
    )
    return record


def test_project_calculation_relationship_lifecycle(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    monkeypatch.setattr(engineering_calculations, "CALCULATIONS_PATH", tmp_path / "calculations.json")
    record = _create_calculation(tmp_path / "calculations.json")
    authorization = _token()
    project = _create_project(authorization)

    # target_type defaults to a calculation now that notes live in Second Brain.
    relationship = asyncio.run(
        project_relationships.create_project_relationship(
            project.id,
            project_relationships.ProjectRelationshipCreateRequest(target_id=record.id),
            authorization,
        )
    )
    assert relationship.target_type == "calculation"
    assert relationship.target_label == "Pump station discharge manifold"
    assert relationship.provenance == "manual"

    graph = asyncio.run(project_relationships.get_project_graph(project.id, authorization))
    assert [node.id for node in graph.nodes] == [f"project:{project.id}", "calculation:calc-1"]
    assert graph.edges[0].kind == "contains"

    asyncio.run(project_relationships.delete_project_relationship(project.id, relationship.id, authorization))
    listed = asyncio.run(project_relationships.list_project_relationships(project.id, authorization))
    assert listed.relationships == []


def test_duplicate_relationship_is_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    monkeypatch.setattr(engineering_calculations, "CALCULATIONS_PATH", tmp_path / "calculations.json")
    _create_calculation(tmp_path / "calculations.json")
    authorization = _token()
    project = _create_project(authorization)
    request = project_relationships.ProjectRelationshipCreateRequest(target_type="calculation", target_id="calc-1")

    asyncio.run(project_relationships.create_project_relationship(project.id, request, authorization))
    try:
        asyncio.run(project_relationships.create_project_relationship(project.id, request, authorization))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409
    else:
        raise AssertionError("Expected duplicate relationship rejection")


def test_new_knowledge_note_links_are_refused_but_old_ones_stay_listed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    authorization = _token()
    project = _create_project(authorization)

    try:
        asyncio.run(
            project_relationships.create_project_relationship(
                project.id,
                project_relationships.ProjectRelationshipCreateRequest(target_type="knowledge_note", target_id="Stormwater.md"),
                authorization,
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
        assert "Second Brain" in exc.detail
    else:
        raise AssertionError("Expected knowledge note links to be refused")

    (tmp_path / "project_relationships.json").write_text(
        json.dumps(
            [
                {
                    "id": "legacy",
                    "project_id": project.id,
                    "target_type": "knowledge_note",
                    "target_id": "Stormwater.md",
                    "target_label": "Stormwater design",
                    "kind": "contains",
                    "provenance": "manual",
                    "created_at": "2026-01-01T00:00:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )
    listed = asyncio.run(project_relationships.list_project_relationships(project.id, authorization))
    assert [(r.target_type, r.target_label) for r in listed.relationships] == [("knowledge_note", "Stormwater design")]
    graph = asyncio.run(project_relationships.get_project_graph(project.id, authorization))
    assert graph.nodes[1].label == "Stormwater design"

def test_project_engineering_standard_relationship_lifecycle(tmp_path: Path, monkeypatch) -> None:
    library = tmp_path / "standards"
    _create_standard(library)
    monkeypatch.setattr(engineering_standards, "LIBRARY_ROOT", library)
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    authorization = _token()
    project = _create_project(authorization)

    relationship = asyncio.run(
        project_relationships.create_project_relationship(
            project.id,
            project_relationships.ProjectRelationshipCreateRequest(
                target_type="engineering_standard",
                target_id="std-1",
                kind="references",
            ),
            authorization,
        )
    )
    assert relationship.target_type == "engineering_standard"
    assert relationship.target_id == "std-1"
    assert relationship.target_label == "AS 3600 · 2018"

    graph = asyncio.run(project_relationships.get_project_graph(project.id, authorization))
    assert len(graph.nodes) == 2
    assert graph.nodes[1].id == "engineering_standard:std-1"
    assert graph.nodes[1].node_type == "engineering_standard"
    assert graph.edges[0].kind == "references"


def test_engineering_standard_relationship_rejects_contains_kind(tmp_path: Path, monkeypatch) -> None:
    library = tmp_path / "standards"
    _create_standard(library)
    monkeypatch.setattr(engineering_standards, "LIBRARY_ROOT", library)
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    authorization = _token()
    project = _create_project(authorization)

    try:
        asyncio.run(
            project_relationships.create_project_relationship(
                project.id,
                project_relationships.ProjectRelationshipCreateRequest(
                    target_type="engineering_standard",
                    target_id="std-1",
                    kind="contains",
                ),
                authorization,
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
    else:
        raise AssertionError("Expected engineering standard 'contains' rejection")


def test_engineering_standard_relationship_requires_existing_document(tmp_path: Path, monkeypatch) -> None:
    library = tmp_path / "standards"
    library.mkdir()
    monkeypatch.setattr(engineering_standards, "LIBRARY_ROOT", library)
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    authorization = _token()
    project = _create_project(authorization)

    try:
        asyncio.run(
            project_relationships.create_project_relationship(
                project.id,
                project_relationships.ProjectRelationshipCreateRequest(
                    target_type="engineering_standard",
                    target_id="missing-doc",
                    kind="references",
                ),
                authorization,
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("Expected missing standard rejection")


def test_project_calculation_relationship_lifecycle(tmp_path: Path, monkeypatch) -> None:
    calculations_path = tmp_path / "engineering-calculations.json"
    _create_calculation(calculations_path)
    monkeypatch.setattr(engineering_calculations, "CALCULATIONS_PATH", calculations_path)
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    authorization = _token()
    project = _create_project(authorization)

    relationship = asyncio.run(
        project_relationships.create_project_relationship(
            project.id,
            project_relationships.ProjectRelationshipCreateRequest(
                target_type="calculation",
                target_id="calc-1",
                kind="contains",
            ),
            authorization,
        )
    )
    assert relationship.target_type == "calculation"
    assert relationship.target_id == "calc-1"
    assert relationship.target_label == "Pump station discharge manifold"

    graph = asyncio.run(project_relationships.get_project_graph(project.id, authorization))
    assert len(graph.nodes) == 2
    assert graph.nodes[1].id == "calculation:calc-1"
    assert graph.nodes[1].node_type == "calculation"
    assert graph.edges[0].kind == "contains"


def test_calculation_relationship_requires_existing_record(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(engineering_calculations, "CALCULATIONS_PATH", tmp_path / "engineering-calculations.json")
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    authorization = _token()
    project = _create_project(authorization)

    try:
        asyncio.run(
            project_relationships.create_project_relationship(
                project.id,
                project_relationships.ProjectRelationshipCreateRequest(
                    target_type="calculation",
                    target_id="missing-calc",
                    kind="contains",
                ),
                authorization,
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("Expected missing calculation rejection")
