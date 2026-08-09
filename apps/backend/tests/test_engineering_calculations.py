import asyncio
import json
from pathlib import Path

import jwt

from app.api import engineering_calculations, engineering_standards, projects


def _token() -> str:
    return "Bearer " + jwt.encode(
        {"sub": projects.AUTH_USERNAME, "iss": "sirisos-api"},
        projects.JWT_SECRET,
        algorithm="HS256",
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


def test_calculation_create_list_get_and_delete(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(engineering_calculations, "CALCULATIONS_PATH", tmp_path / "engineering-calculations.json")
    authorization = _token()

    created = asyncio.run(
        engineering_calculations.create_calculation(
            engineering_calculations.CalculationCreateRequest(
                calculator_id="minorLoss",
                title="Pump station discharge manifold",
                inputs={"flowM3s": 0.05, "diameterM": 0.20, "sumKValues": 1.5},
                results=[
                    engineering_calculations.CalculationResultItem(label="Flow", value="0.050 m³/s"),
                    engineering_calculations.CalculationResultItem(label="Flow", value="50 L/s"),
                    engineering_calculations.CalculationResultItem(label="Minor headloss", value="0.194 m"),
                ],
                notes="Two 90° elbows plus a gate valve.",
            ),
            authorization,
        )
    )
    assert created.calculator_id == "minorLoss"
    assert created.title == "Pump station discharge manifold"
    assert created.inputs["sumKValues"] == 1.5
    # Duplicate labels (e.g. flow shown in two units) must both survive as an ordered list.
    assert [item.label for item in created.results] == ["Flow", "Flow", "Minor headloss"]
    assert [item.value for item in created.results] == ["0.050 m³/s", "50 L/s", "0.194 m"]
    assert engineering_calculations.CALCULATIONS_PATH.exists()

    fetched = asyncio.run(engineering_calculations.get_calculation(created.id, authorization))
    assert fetched.id == created.id

    listed = asyncio.run(engineering_calculations.list_calculations(authorization))
    assert [item.id for item in listed.calculations] == [created.id]

    asyncio.run(engineering_calculations.delete_calculation(created.id, authorization))
    listed_after = asyncio.run(engineering_calculations.list_calculations(authorization))
    assert listed_after.calculations == []


def test_calculation_authentication_required(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(engineering_calculations, "CALCULATIONS_PATH", tmp_path / "engineering-calculations.json")
    try:
        asyncio.run(engineering_calculations.list_calculations(None))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 401
    else:
        raise AssertionError("Expected authentication failure")


def test_get_missing_calculation_returns_404(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(engineering_calculations, "CALCULATIONS_PATH", tmp_path / "engineering-calculations.json")
    authorization = _token()
    try:
        asyncio.run(engineering_calculations.get_calculation("missing-id", authorization))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("Expected missing calculation rejection")


def test_calculation_can_cite_a_standard(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(engineering_calculations, "CALCULATIONS_PATH", tmp_path / "engineering-calculations.json")
    library = tmp_path / "standards"
    _create_standard(library)
    monkeypatch.setattr(engineering_standards, "LIBRARY_ROOT", library)
    authorization = _token()

    created = asyncio.run(
        engineering_calculations.create_calculation(
            engineering_calculations.CalculationCreateRequest(
                calculator_id="hazenWilliams",
                title="Rising main headloss",
                inputs={"flowM3s": 0.05},
                results=[engineering_calculations.CalculationResultItem(label="Headloss", value="1.12 m")],
                cited_standard_id="std-1",
            ),
            authorization,
        )
    )
    assert created.cited_standard_id == "std-1"
    assert created.cited_standard_label == "AS 3600 · 2018"

    # Citation label is resolved fresh on read, not frozen at creation time.
    fetched = asyncio.run(engineering_calculations.get_calculation(created.id, authorization))
    assert fetched.cited_standard_label == "AS 3600 · 2018"

    listed = asyncio.run(engineering_calculations.list_calculations(authorization))
    assert listed.calculations[0].cited_standard_label == "AS 3600 · 2018"


def test_calculation_rejects_citing_a_missing_standard(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(engineering_calculations, "CALCULATIONS_PATH", tmp_path / "engineering-calculations.json")
    library = tmp_path / "standards"
    library.mkdir()
    monkeypatch.setattr(engineering_standards, "LIBRARY_ROOT", library)
    authorization = _token()

    try:
        asyncio.run(
            engineering_calculations.create_calculation(
                engineering_calculations.CalculationCreateRequest(
                    calculator_id="hazenWilliams",
                    title="Rising main headloss",
                    inputs={},
                    results=[],
                    cited_standard_id="missing-doc",
                ),
                authorization,
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("Expected missing standard rejection")


def test_calculation_citation_survives_when_standard_later_removed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(engineering_calculations, "CALCULATIONS_PATH", tmp_path / "engineering-calculations.json")
    library = tmp_path / "standards"
    _create_standard(library)
    monkeypatch.setattr(engineering_standards, "LIBRARY_ROOT", library)
    authorization = _token()

    created = asyncio.run(
        engineering_calculations.create_calculation(
            engineering_calculations.CalculationCreateRequest(
                calculator_id="hazenWilliams",
                title="Rising main headloss",
                inputs={},
                results=[],
                cited_standard_id="std-1",
            ),
            authorization,
        )
    )

    # Simulate the cited standard becoming unreachable (e.g. removed from disk).
    import shutil

    shutil.rmtree(library / "std-1")

    fetched = asyncio.run(engineering_calculations.get_calculation(created.id, authorization))
    assert fetched.cited_standard_id == "std-1"
    assert fetched.cited_standard_label == "AS 3600 · 2018"
