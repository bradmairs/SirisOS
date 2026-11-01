"""6.5: the gym: routines, logging, what to lift next, records, plates, the week."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.gym import service, store
from app.tasks import service as tasks
from tests.test_hub import AUTH

TODAY = date(2026, 11, 4)  # a Wednesday


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_GYM_PATH", str(tmp_path / "gym.json"))
    monkeypatch.setattr(tasks, "today", lambda: TODAY)
    return TestClient(app)


def session(sid: str, day: str, sets: list[tuple[float, int]], exercise: str = "bench-press", routine: str | None = None, d: int | None = None) -> dict:
    return {"id": sid, "title": "Push", "started_at": f"{day}T07:00:00+00:00", "ended_at": f"{day}T08:05:00+00:00", "routine_id": routine, "day": d,
            "entries": [{"exercise": exercise, "sets": [{"weight": 20, "reps": 10, "type": "warmup"}] + [{"weight": w, "reps": r} for w, r in sets]}]}


def test_epley_and_plates():
    assert service.e1rm(100, 5) == 116.7 and service.e1rm(140, 1) == 140 and service.e1rm(60, 20) is None
    assert service.plates(102.5, 20, [25, 20, 15, 10, 5, 2.5, 1.25]) == {"per_side": [25, 15, 1.25], "left": 0.0, "loaded": 102.5}
    assert service.plates(15, 20, [25])["left"] == -5


def test_a_routine_from_a_template_plans_the_next_day_with_what_to_lift(client):
    r = client.post("/api/v1/gym/routines", headers=AUTH, json={"template": "tpl-ppl"}).json()
    assert r["active"] and [d["name"] for d in r["days"]] == ["Push", "Pull", "Legs"]
    plan = client.get(f"/api/v1/gym/plan?routine={r['id']}", headers=AUTH).json()
    assert plan["title"] == "Push, pull, legs: Push" and plan["exercises"][0]["suggest"]["weight"] is None
    # Push done, every set of bench at 80 reached the top of 5-8: next push adds 2.5; next day is Pull.
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("s1", "2026-11-02", [(80, 8), (80, 8), (80, 8), (80, 8)], routine=r["id"], d=0))
    assert client.get(f"/api/v1/gym/plan?routine={r['id']}", headers=AUTH).json()["day"] == 1
    push = client.get(f"/api/v1/gym/plan?routine={r['id']}&day=0", headers=AUTH).json()["exercises"][0]
    assert push["suggest"]["weight"] == 82.5 and push["suggest"]["reps"] == 5 and len(push["last"]) == 4  # warm-up left out


def test_records_and_what_a_session_set(client):
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("s1", "2026-10-28", [(80, 5), (80, 5), (80, 4)]))
    first = client.post("/api/v1/gym/sessions", headers=AUTH, json=session("s2", "2026-11-03", [(85, 5), (85, 5), (85, 3)])).json()
    kinds = {r["kind"] for r in first["records"]}
    assert {"heaviest", "e1rm", "5rm"} <= kinds
    assert first["summary"]["sets"] == 3 and first["summary"]["minutes"] == 65 and first["summary"]["volume"] == 85 * 13
    # Sending the same session again replaces it, never doubles it (the offline outbox may retry).
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("s2", "2026-11-03", [(85, 5), (85, 5), (85, 3)]))
    detail = client.get("/api/v1/gym/exercises/bench-press", headers=AUTH).json()
    assert len(detail["history"]) == 2 and detail["records"]["heaviest"]["weight"] == 85
    assert detail["records"]["rep_max"]["5"] == {"weight": 85, "date": "2026-11-03"} and detail["records"]["e1rm"]["value"] == 99.2
    assert [p["date"] for p in detail["series"]] == ["2026-10-28", "2026-11-03"]


def test_the_week_by_muscle_streak_and_own_exercises(client):
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("s1", "2026-10-27", [(80, 5)]))
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("s2", "2026-11-03", [(80, 5), (80, 5)]))
    over = client.get("/api/v1/gym", headers=AUTH).json()
    assert over["week"]["sessions"] == 1 and over["week"]["sets_by_muscle"] == {"chest": 2, "triceps": 1, "shoulders": 1}
    assert over["streak_weeks"] == 2 and over["recent"][0]["id"] == "s2"
    mine = client.post("/api/v1/gym/exercises", headers=AUTH, json={"name": "Landmine Press", "primary": "shoulders", "secondary": ["chest"], "equipment": "barbell"}).json()
    assert mine["id"].startswith("my-") and any(e["id"] == mine["id"] for e in client.get("/api/v1/gym", headers=AUTH).json()["exercises"])
    assert client.post("/api/v1/gym/exercises", headers=AUTH, json={"name": "x", "primary": "elbows"}).status_code == 422
    assert client.get("/api/v1/gym/sessions?month=2026-11", headers=AUTH).json()["sessions"][0]["id"] == "s2"
