"""Server-side calculators (ADR 110): parity with the Calculators screen,
the API, and SirisAI's service key."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.engineering import calculators
from app.entrypoint import app
from tests.test_hub import AUTH

CASES = json.loads((Path(__file__).resolve().parents[2] / "web" / "src" / "engineering" / "calculator-cases.json").read_text())
KEY = "k" * 32


@pytest.mark.parametrize("case", CASES, ids=[f"{c['calculator']}-{i}" for i, c in enumerate(CASES)])
def test_same_results_as_the_typescript(case) -> None:
    calculator = calculators.BY_ID[case["calculator"]]
    if "error" in case:
        with pytest.raises(calculators.InputError, match=case["error"]):
            calculator.compute(case["inputs"])
    else:
        assert calculator.compute(case["inputs"]) == case["results"]


def test_every_calculator_is_covered() -> None:
    assert {c["calculator"] for c in CASES} == set(calculators.BY_ID)


def test_to_fixed_rounds_like_javascript() -> None:
    assert calculators.fixed(0.125, 2) == "0.13"  # Python's format() says 0.12
    assert calculators.fixed(2.5, 0) == "3"
    assert calculators.fixed(-0.0, 2) == "0.00" and calculators.fixed(-0.0001, 2) == "-0.00"
    assert calculators.fixed(float("inf"), 2) == "Infinity"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_api_lists_and_runs(client) -> None:
    listed = client.get("/api/v1/engineering/calculators", headers=AUTH).json()["calculators"]
    assert [c["id"] for c in listed][:2] == ["fullPipe", "partFullPipe"]
    assert listed[0]["fields"][0] == {"key": "d", "label": "Internal diameter", "unit": "m", "initial": "0.45"}
    ran = client.post("/api/v1/engineering/calculators/fullPipe/run", json={"inputs": {"d": 0.45, "n": 0.013, "s": 0.005}}, headers=AUTH).json()
    assert ran["results"][0] == {"label": "Flow", "value": "0.202 m³/s"}


def test_api_errors(client) -> None:
    assert client.get("/api/v1/engineering/calculators").status_code == 401
    assert client.post("/api/v1/engineering/calculators/nope/run", json={"inputs": {}}, headers=AUTH).status_code == 404
    missing = client.post("/api/v1/engineering/calculators/fullPipe/run", json={"inputs": {"d": 0.45}}, headers=AUTH)
    assert missing.status_code == 422 and "Manning n (n) is required" in missing.json()["detail"]
    bad = client.post("/api/v1/engineering/calculators/partFullPipe/run", json={"inputs": {"d": 0.3, "y": 0.45, "n": 0.013, "s": 0.005}}, headers=AUTH)
    assert bad.status_code == 422 and bad.json()["detail"] == "depth cannot exceed diameter"


def test_service_key_opens_only_read_and_compute_routes(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SIRISOS_SERVICE_KEY", KEY)
    service = {"Authorization": f"Bearer {KEY}"}
    assert client.get("/api/v1/engineering/calculators", headers=service).status_code == 200
    assert client.post("/api/v1/engineering/calculators/fullPipe/run", json={"inputs": {"d": 0.45, "n": 0.013, "s": 0.005}}, headers=service).status_code == 200
    assert client.get("/api/v1/projects", headers=service).status_code == 200
    # Never anything that writes, and not the rest of the API either.
    assert client.post("/api/v1/projects", json={"name": "x"}, headers=service).status_code == 403
    assert client.post("/api/v1/engineering/calculations", json={}, headers=service).status_code == 403
    assert client.get("/api/v1/brief", headers=service).status_code == 403
    assert client.get("/api/v1/auth/me", headers=service).status_code == 403
    # A wrong key is just a bad token; the session token still works as before.
    assert client.get("/api/v1/engineering/calculators", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/api/v1/engineering/calculators", headers=AUTH).status_code == 200


def test_a_short_service_key_is_ignored(client, monkeypatch) -> None:
    monkeypatch.setenv("SIRISOS_SERVICE_KEY", "short")
    assert client.get("/api/v1/engineering/calculators", headers={"Authorization": "Bearer short"}).status_code == 401
