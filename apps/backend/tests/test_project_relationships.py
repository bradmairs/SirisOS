import asyncio
from pathlib import Path

import jwt

from app.api import knowledge, project_relationships, projects


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


def test_project_knowledge_relationship_lifecycle(tmp_path: Path, monkeypatch) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Stormwater.md").write_text("# Stormwater design\n\n#siris/engineering\n", encoding="utf-8")
    monkeypatch.setattr(knowledge, "VAULT_ROOT", vault)
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    authorization = _token()
    project = _create_project(authorization)

    relationship = asyncio.run(
        project_relationships.create_project_relationship(
            project.id,
            project_relationships.ProjectRelationshipCreateRequest(
                target_id="Stormwater.md",
                kind="contains",
            ),
            authorization,
        )
    )
    assert relationship.project_id == project.id
    assert relationship.target_type == "knowledge_note"
    assert relationship.target_id == "Stormwater.md"
    assert relationship.target_label == "Stormwater design"
    assert relationship.provenance == "manual"
    assert (tmp_path / "project_relationships.json").exists()

    listed = asyncio.run(project_relationships.list_project_relationships(project.id, authorization))
    assert [item.id for item in listed.relationships] == [relationship.id]

    graph = asyncio.run(project_relationships.get_project_graph(project.id, authorization))
    assert graph.project_id == project.id
    assert graph.nodes[0].id == f"project:{project.id}"
    assert graph.nodes[0].center is True
    assert graph.nodes[0].node_type == "project"
    assert len(graph.nodes) == 2
    assert graph.nodes[1].id == "knowledge_note:Stormwater.md"
    assert graph.nodes[1].label == "Stormwater design"
    assert len(graph.edges) == 1
    assert graph.edges[0].kind == "contains"
    assert graph.edges[0].provenance == "manual"

    asyncio.run(
        project_relationships.delete_project_relationship(
            project.id,
            relationship.id,
            authorization,
        )
    )
    listed = asyncio.run(project_relationships.list_project_relationships(project.id, authorization))
    assert listed.relationships == []


def test_duplicate_relationship_is_rejected(tmp_path: Path, monkeypatch) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Server.md").write_text("# Linux Server\n", encoding="utf-8")
    monkeypatch.setattr(knowledge, "VAULT_ROOT", vault)
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    authorization = _token()
    project = _create_project(authorization)
    request = project_relationships.ProjectRelationshipCreateRequest(target_id="Server.md")

    asyncio.run(project_relationships.create_project_relationship(project.id, request, authorization))
    try:
        asyncio.run(project_relationships.create_project_relationship(project.id, request, authorization))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 409
    else:
        raise AssertionError("Expected duplicate relationship rejection")


def test_relationship_requires_existing_note(tmp_path: Path, monkeypatch) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setattr(knowledge, "VAULT_ROOT", vault)
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    authorization = _token()
    project = _create_project(authorization)

    try:
        asyncio.run(
            project_relationships.create_project_relationship(
                project.id,
                project_relationships.ProjectRelationshipCreateRequest(target_id="Missing.md"),
                authorization,
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("Expected missing note rejection")
