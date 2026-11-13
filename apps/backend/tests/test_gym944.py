"""9.44: every exercise's helper muscles, filled from its name, and counted in recovery."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.gym import anatomy, coach, library, store
from tests.test_hub import AUTH


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_GYM_PATH", str(tmp_path / "gym.json"))
    return TestClient(app, headers=AUTH)


def test_every_built_in_compound_names_its_helpers_and_the_table_agrees():
    isolations = {"tricep-pushdown", "skull-crusher", "wrist-curl", "leg-extension", "hip-abduction", "standing-calf-raise",
                  "seated-calf-raise", "crunch", "cable-crunch", "russian-twist"}
    assert {k for k, v in library.BUILTIN.items() if not v["secondary"]} == isolations
    for v in library.BUILTIN.values():
        assert v["primary"] not in v["secondary"]
        assert all(m in library.MUSCLES for m in v["secondary"])
        assert (anatomy.muscles_for(v["name"]) or ("",))[0] == v["primary"], v["name"]


@pytest.mark.parametrize("name,primary,helpers", [
    ("Cable V Bar Pulldown", "back", ("biceps", "forearms")), ("Wide Grip Lat Pulldown", "back", ("biceps", "forearms")),
    ("Seated Tricep Press", "triceps", ("chest", "shoulders")), ("Rear Delt Fly", "shoulders", ("back",)),
    ("Incline Smith Press", "chest", ("shoulders", "triceps")), ("Rowing Machine", "cardio", ("back", "quads")),
    ("Smith Machine Squat", "quads", ("glutes", "hamstrings")), ("Reverse Grip Curl", "biceps", ("forearms",)),
    ("Push-up", "chest", ("triceps", "shoulders")), ("Leg Extension", "quads", ()),
])
def test_names_say_the_movement(name, primary, helpers):
    assert anatomy.muscles_for(name) == (primary, helpers)
    assert anatomy.muscles_for("Thing I made up") is None


def test_your_exercises_get_their_helpers_once_with_a_copy_first(tmp_path, monkeypatch):
    monkeypatch.setenv("SIRISOS_GYM_PATH", str(tmp_path / "gym.json"))
    recent = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT07:00:00+00:00")
    raw = {"exercises": [
        {"id": "my-a", "name": "Cable V Bar Pulldown", "primary": "back"},  # no helpers yet
        {"id": "my-b", "name": "Hammer Strength Row", "primary": "full body"},  # only guessed
        {"id": "my-c", "name": "Seated Tricep Press", "primary": "chest"},  # your main muscle is kept
        {"id": "my-d", "name": "Bench Thing", "primary": "chest", "secondary": ["shoulders"]},  # your helpers are kept
        {"id": "my-e", "name": "Mystery", "primary": "abs"}],  # the name says nothing
        "sessions": [{"id": "s1", "started_at": recent, "entries": [{"exercise": x, "sets": [{"weight": 50, "reps": 8, "done": True}]}
                                                                    for x in ("my-a", "my-b", "my-c", "my-d", "my-e")]},
                     {"id": "old", "started_at": "2025-01-01T07:00:00+00:00", "entries": []}]}
    (tmp_path / "gym.json").write_text(json.dumps(raw))
    doc = store.load()
    mine = {e.id: e for e in doc.exercises}
    assert mine["my-a"].secondary == ["biceps", "forearms"]
    assert (mine["my-b"].primary, mine["my-b"].secondary) == ("back", ["biceps", "forearms"])
    assert (mine["my-c"].primary, mine["my-c"].secondary) == ("chest", ["shoulders"])  # chest is yours; it doesn't help itself
    assert mine["my-d"].secondary == ["shoulders"] and mine["my-e"].secondary == []
    assert doc.muscles_filled and list(tmp_path.glob("gym.before-muscles.*.json"))
    sessions = {s.id: s for s in doc.sessions}
    assert sessions["s1"].ai_pending and not sessions["old"].ai_pending  # this week goes to SirisAI again
    mine_again = {e.id: e for e in store.load().exercises}  # only once
    assert mine_again["my-e"].secondary == []


def test_a_helper_muscle_is_tired_too_but_recovers_sooner(client):
    day = "2026-11-10"
    client.post("/api/v1/gym/sessions", json={"id": "row", "title": "Pull", "started_at": f"{day}T07:00:00+00:00", "ended_at": f"{day}T08:00:00+00:00",
                                              "entries": [{"exercise": "barbell-row", "sets": [{"weight": 60, "reps": 8, "done": True}] * 3}]})
    rec = {r["muscle"]: r for r in coach.recovery(store.load(), datetime(2026, 11, 11, 7, tzinfo=timezone.utc))}
    assert rec["back"]["via"] == "main" and rec["back"]["ready"] == 50  # 24 of 48 h
    assert rec["biceps"]["via"] == "helper" and rec["biceps"]["ready"] == 100  # 24 h of the 18 a helper needs
    rec = {r["muscle"]: r for r in coach.recovery(store.load(), datetime(2026, 11, 10, 16, tzinfo=timezone.utc))}
    assert rec["biceps"]["ready"] == 50 and rec["forearms"]["ready"] == 75  # 9 of 18 h; 9 of 12 h
    assert rec["chest"]["ready"] is None


def test_new_imports_and_the_form_get_helpers(client):
    from app.gym import importer

    doc = store.GymDoc()
    importer.commit(doc, [{"date": datetime(2026, 11, 1, 7), "exercise": "Chest Supported T-Bar Row", "weight": 40, "reps": 10, "order": (0, 1)}], {})
    ex = next(e for e in doc.exercises if e.name == "Chest Supported T-Bar Row")
    assert (ex.primary, ex.secondary) == ("back", ["biceps", "forearms"])
    assert client.get("/api/v1/gym/anatomy?name=Incline Hammer Curl").json() == {"primary": "biceps", "secondary": ["forearms"]}
    assert client.get("/api/v1/gym/anatomy?name=Thing").json() == {"primary": None, "secondary": []}
    mine = client.post("/api/v1/gym/exercises", json={"name": "Landmine Press", "primary": "chest", "equipment": "barbell"}).json()
    changed = client.put(f"/api/v1/gym/exercises/{mine['id']}", json={"primary": "shoulders"}).json()
    assert changed["secondary"] == ["triceps"]  # a new main muscle brings the helpers the name says
