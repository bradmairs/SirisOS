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


def test_a_saved_calculation_prints_as_a_one_page_sheet(tmp_path: Path, monkeypatch) -> None:
    import io

    from fastapi.testclient import TestClient
    from pypdf import PdfReader

    from app.entrypoint import app

    monkeypatch.setattr(engineering_calculations, "CALCULATIONS_PATH", tmp_path / "engineering-calculations.json")
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    client = TestClient(app)
    headers = {"Authorization": _token()}
    created = client.post("/api/v1/engineering/calculations", headers=headers, json={
        "calculator_id": "hazenWilliams", "title": "Rising main (Shepparton) – check",
        "inputs": {"q": 0.05, "d": 0.2, "l": 100, "c": 140},
        "results": [{"label": "Friction headloss", "value": "2.21 m"}, {"label": "Velocity", "value": "1.59 m/s"}],
        "notes": "Existing DN200 PVC. " * 30,
    }).json()
    response = client.get(f"/api/v1/engineering/calculations/{created['id']}/pdf", headers=headers)
    assert response.status_code == 200 and response.headers["content-type"] == "application/pdf"
    assert 'filename="Rising main -Shepparton- - check.pdf"' in response.headers["content-disposition"]
    reader = PdfReader(io.BytesIO(response.content))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    for expected in ("Rising main (Shepparton) – check", "Hazen–Williams headloss", "Internal diameter", "0.2 m",
                     "Hazen–Williams C", "Friction headloss", "2.21 m", "Checked by", "Prepared by: Brad"):
        assert expected in text, expected
    assert reader.metadata.title == "Rising main (Shepparton) – check"
    assert client.get(f"/api/v1/engineering/calculations/{created['id']}/pdf").status_code == 401
    assert client.get("/api/v1/engineering/calculations/nope/pdf", headers=headers).status_code == 404


def test_the_sheet_prints_inputs_saved_by_label_too() -> None:
    import io

    from pypdf import PdfReader

    record = engineering_calculations.CalculationRecord(
        id="c1", calculator_id="fullPipe", title="Trunk main check",
        inputs={"Internal diameter (m)": 0.45, "Manning n": 0.013}, results=[], created_at="2026-10-17T00:00:00+00:00")
    text = PdfReader(io.BytesIO(engineering_calculations.calculation_pdf(record))).pages[0].extract_text()
    assert "Internal diameter (m)" in text and "0.45" in text and "Manning n" in text and "0.013" in text
