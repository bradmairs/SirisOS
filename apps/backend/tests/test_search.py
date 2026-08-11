import asyncio
import json
from pathlib import Path

import jwt

from app.api import engineering_calculations, engineering_standards, projects, search, siris_memory


def _token() -> str:
    return "Bearer " + jwt.encode(
        {"sub": search.AUTH_USERNAME, "iss": "sirisos-api"},
        search.JWT_SECRET,
        algorithm="HS256",
    )


def test_search_requires_authentication() -> None:
    try:
        asyncio.run(search.search(q="anything", authorization=None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 401
    else:
        raise AssertionError("Expected authentication failure")


def test_search_finds_matching_project(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    monkeypatch.setattr(engineering_calculations, "CALCULATIONS_PATH", tmp_path / "calculations.json")
    monkeypatch.setattr(engineering_standards, "LIBRARY_ROOT", tmp_path / "standards")
    monkeypatch.setattr(siris_memory, "MEMORY_PATH", tmp_path / "memory.json")

    asyncio.run(
        projects.create_project(
            projects.ProjectCreateRequest(name="Sydney Water rising main", kind="engineering"),
            authorization=_token(),
        )
    )

    results = asyncio.run(search.search(q="rising main", authorization=_token()))

    assert any(item.module == "projects" and "Sydney Water" in item.title for item in results)


def test_search_finds_matching_saved_calculation(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    monkeypatch.setattr(engineering_calculations, "CALCULATIONS_PATH", tmp_path / "calculations.json")
    monkeypatch.setattr(engineering_standards, "LIBRARY_ROOT", tmp_path / "standards")
    monkeypatch.setattr(siris_memory, "MEMORY_PATH", tmp_path / "memory.json")

    asyncio.run(
        engineering_calculations.create_calculation(
            engineering_calculations.CalculationCreateRequest(
                calculator_id="hazenWilliams",
                title="Rising main headloss check",
                inputs={},
                results=[],
            ),
            authorization=_token(),
        )
    )

    results = asyncio.run(search.search(q="headloss", authorization=_token()))

    assert any(item.module == "engineering" and "headloss" in item.title.lower() for item in results)


def test_search_finds_matching_standard(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    monkeypatch.setattr(engineering_calculations, "CALCULATIONS_PATH", tmp_path / "calculations.json")
    library = tmp_path / "standards"
    monkeypatch.setattr(engineering_standards, "LIBRARY_ROOT", library)
    monkeypatch.setattr(siris_memory, "MEMORY_PATH", tmp_path / "memory.json")

    directory = library / "std-1"
    directory.mkdir(parents=True)
    (directory / "metadata.json").write_text(
        json.dumps(
            {
                "id": "std-1",
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

    results = asyncio.run(search.search(q="AS 3600", authorization=_token()))

    assert any(item.module == "engineering" and item.title == "AS 3600" for item in results)


def test_search_excludes_archived_standards(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    monkeypatch.setattr(engineering_calculations, "CALCULATIONS_PATH", tmp_path / "calculations.json")
    library = tmp_path / "standards"
    monkeypatch.setattr(engineering_standards, "LIBRARY_ROOT", library)
    monkeypatch.setattr(siris_memory, "MEMORY_PATH", tmp_path / "memory.json")

    directory = library / "std-1"
    directory.mkdir(parents=True)
    (directory / "metadata.json").write_text(
        json.dumps(
            {
                "id": "std-1",
                "title": "Old edition",
                "authority": "Standards Australia",
                "reference": "AS 9999",
                "filename": "as9999.pdf",
                "uploaded_at": "2026-01-01T00:00:00+00:00",
                "pages": 1,
                "indexed": True,
                "active": False,
            }
        ),
        encoding="utf-8",
    )

    results = asyncio.run(search.search(q="AS 9999", authorization=_token()))

    assert not any(item.module == "engineering" and item.title == "AS 9999" for item in results)


def test_search_finds_matching_siris_memory(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    monkeypatch.setattr(engineering_calculations, "CALCULATIONS_PATH", tmp_path / "calculations.json")
    monkeypatch.setattr(engineering_standards, "LIBRARY_ROOT", tmp_path / "standards")
    monkeypatch.setattr(siris_memory, "MEMORY_PATH", tmp_path / "memory.json")

    asyncio.run(
        siris_memory.create_memory(
            siris_memory.MemoryCreateRequest(
                memory_class="decision", content="Used Class 3 pipe on the rising main."
            ),
            authorization=_token(),
        )
    )

    results = asyncio.run(search.search(q="class 3 pipe", authorization=_token()))

    assert any(item.module == "siris" for item in results)


def test_search_degrades_gracefully_when_a_store_is_corrupted(tmp_path, monkeypatch) -> None:
    corrupted = tmp_path / "projects.json"
    corrupted.write_text("not valid json", encoding="utf-8")
    monkeypatch.setattr(projects, "PROJECTS_PATH", corrupted)
    monkeypatch.setattr(engineering_calculations, "CALCULATIONS_PATH", tmp_path / "calculations.json")
    monkeypatch.setattr(engineering_standards, "LIBRARY_ROOT", tmp_path / "standards")
    monkeypatch.setattr(siris_memory, "MEMORY_PATH", tmp_path / "memory.json")

    asyncio.run(
        siris_memory.create_memory(
            siris_memory.MemoryCreateRequest(memory_class="fact", content="Homelab runs on a Linux server."),
            authorization=_token(),
        )
    )

    # A corrupted projects store must not prevent search from returning
    # results from other, healthy sources.
    results = asyncio.run(search.search(q="linux server", authorization=_token()))

    assert any(item.module == "siris" for item in results)
