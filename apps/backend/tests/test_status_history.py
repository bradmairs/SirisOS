"""System status: health history per app."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.hub import history
from tests.test_hub import AUTH, apps  # noqa: F401 - the fixture

NOW = 1_800_000_000.0


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("SIRISOS_STATUS_HISTORY_PATH", str(tmp_path / "status.json"))
    history.reset()
    yield tmp_path / "status.json"
    history.reset()


def test_samples_are_thinned_but_state_changes_always_kept(store):
    assert history.record("archive", {"state": "ok", "latency_ms": 40}, now=NOW)
    assert not history.record("archive", {"state": "ok", "latency_ms": 41}, now=NOW + 60)  # too soon, same state
    assert history.record("archive", {"state": "down", "detail": "Timed out"}, now=NOW + 90)  # a change: kept
    assert history.record("archive", {"state": "ok", "latency_ms": 50}, now=NOW + 400)
    assert store.exists()
    history.reset()  # survives a restart
    assert history.summary("archive", now=NOW + 500)["samples"] == 3
    # Older than 7 days is dropped on the next record.
    history.record("archive", {"state": "ok", "latency_ms": 30}, now=NOW + 8 * 86400)
    assert history.summary("archive", now=NOW + 8 * 86400)["samples"] == 1


def test_summary_gives_uptime_latency_timeline_and_incidents():
    t = NOW - 86400 + 60
    for i in range(24):  # one sample an hour; down for two hours
        state = "down" if i in (10, 11) else "ok"
        history.record("reviewer", {"state": state, "latency_ms": 100 if state == "ok" else None, "detail": "Timed out" if state == "down" else ""}, now=t + i * 3600)
    s = history.summary("reviewer", now=NOW)
    assert s["uptime_24h"] == round(100 * 22 / 24, 1) and s["latency_ms_24h"] == 100
    assert len(s["hours"]) == 24 and s["hours"][10] == "down" and s["hours"][0] == "ok"
    assert s["incidents"] == [{"at": round(t + 10 * 3600), "detail": "Timed out", "minutes": 120}]
    assert s["last_problem"]["state"] == "down"
    assert history.summary("nothing", now=NOW)["uptime_24h"] is None


def test_status_route_lists_configured_apps_with_history(apps):
    client = TestClient(app)
    body = client.get("/api/v1/hub/status", headers=AUTH).json()
    ids = [a["id"] for a in body["apps"]]
    assert "sirisai" in ids and "archive" in ids
    archive = next(a for a in body["apps"] if a["id"] == "archive")
    assert archive["status"]["state"] == "ok" and archive["samples"] >= 1 and archive["uptime_24h"] == 100.0
    assert body["sample_every_minutes"] == 5
    assert client.get("/api/v1/hub/status").status_code == 401
