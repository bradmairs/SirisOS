import asyncio
from pathlib import Path

import jwt

from app.api import engineering_calculations, projects


def _token() -> str:
    return "Bearer " + jwt.encode(
        {"sub": projects.AUTH_USERNAME, "iss": "sirisos-api"},
        projects.JWT_SECRET,
        algorithm="HS256",
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
