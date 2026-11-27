"""11.14: session notes read and acted on, with approval."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.gym import notes, store
from app.tasks import service as tasks
from tests.test_hub import AUTH

TODAY = date(2026, 11, 27)
ENTRIES = [{"exercise": "bench-press", "name": "Bench Press"}, {"exercise": "back-squat", "name": "Back Squat"},
           {"exercise": "overhead-press", "name": "Overhead Press"}, {"exercise": "lat-pulldown", "name": "Lat Pulldown"}]


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_GYM_PATH", str(tmp_path / "gym.json"))
    monkeypatch.delenv("OLLAMA_URL", raising=False)  # rules only, here
    monkeypatch.setattr(tasks, "today", lambda: TODAY)
    return TestClient(app, headers=AUTH)


def session(sid: str, day: str, exercises=("bench-press", "back-squat", "overhead-press"), note: str | None = None, weight: float = 80):
    return {"id": sid, "title": "Push", "started_at": f"{day}T07:00:00+11:00", "ended_at": f"{day}T07:45:00+11:00",
            **({"note": note} if note else {}), "entries": [{"exercise": e, "sets": [{"weight": weight, "reps": 8}] * 3} for e in exercises]}


@pytest.mark.parametrize("note, want", [
    ("Left shoulder twinged on the overhead press", [("spare", "shoulder")]),
    ("Squat rack was taken so I did leg press", [("swap", "back-squat")]),
    ("Bench felt light today, could go heavier", [("up", "bench-press")]),
    ("Couldn't finish the last set of pulldowns", [("down", "lat-pulldown")]),
    ("Lower back a bit tight after squats", [("spare", "lower back")]),
    ("Good session", []),
    ("Imported", []),
])
def test_the_rules_read_what_a_note_asks(note, want):
    assert [(a["kind"], a.get("area") or a.get("exercise")) for a in notes.rules(note, ENTRIES)] == want


def test_a_note_at_finishing_offers_suggestions_and_nothing_changes_until_approved(client):
    got = client.post("/api/v1/gym/sessions", json=session("a", "2026-11-26", note="Bench felt easy. Right knee sore after squats.")).json()
    kinds = sorted((a["kind"], a.get("area") or a.get("exercise")) for a in got["note_actions"])
    assert kinds == [("spare", "knee"), ("up", "bench-press")]
    assert all(a["text"] for a in got["note_actions"])
    doc = store.load()
    assert not doc.niggles and not doc.nudges  # only suggested
    overview = client.get("/api/v1/gym").json()
    assert len(overview["note_actions"]) == 2


def test_approving_does_what_it_says_and_a_step_is_used_once(client):
    client.post("/api/v1/gym/routines", json={"routine": {"name": "R", "active": True, "days": [{"name": "A", "exercises": [{"exercise": "bench-press", "sets": 3, "reps": "8-12"}]}]}})
    got = client.post("/api/v1/gym/sessions", json=session("a", "2026-11-26", exercises=("bench-press",), note="Bench felt light")).json()
    up = got["note_actions"][0]
    rid = next(r.id for r in store.load().routines if r.name == "R")
    before = client.get(f"/api/v1/gym/plan?routine={rid}").json()["exercises"][0]["suggest"]["weight"]
    done = client.post(f"/api/v1/gym/note-actions/{up['id']}", json={"act": "apply"}).json()
    assert "+2.5" in done["done"] and done["actions"] == []
    after = client.get(f"/api/v1/gym/plan?routine={rid}").json()["exercises"][0]
    assert after["suggest"]["weight"] == before + 2.5 and after["suggest"]["why"].startswith("Your note said it felt easy")
    client.post("/api/v1/gym/sessions", json=session("b", "2026-11-27", exercises=("bench-press",), weight=after["suggest"]["weight"]))
    assert "bench-press" not in store.load().nudges  # used
    assert client.post(f"/api/v1/gym/note-actions/{up['id']}", json={"act": "apply"}).status_code == 404  # answered


def test_a_sore_spot_becomes_a_niggle_and_taken_gear_a_swap_at_that_gym(client):
    got = client.post("/api/v1/gym/sessions", json=session("a", "2026-11-26", note="Shoulder hurt on the overhead press; squat rack was busy")).json()
    by = {a["kind"]: a for a in got["note_actions"]}
    client.post(f"/api/v1/gym/note-actions/{by['spare']['id']}", json={"act": "apply"})
    assert [n.area for n in store.load().niggles] == ["shoulder"]
    out = client.post(f"/api/v1/gym/note-actions/{by['swap']['id']}", json={"act": "apply"}).json()
    doc = store.load()
    home = next(g for g in doc.settings.gyms if g.id == doc.settings.current_gym)
    assert "back-squat" in home.swaps and "from now on" in out["done"]


def test_no_leaves_it_and_a_note_added_after_is_read_too(client):
    client.post("/api/v1/gym/sessions", json=session("a", "2026-11-26"))
    got = client.put("/api/v1/gym/sessions/a/note", json={"note": "Lat pulldown was too heavy"}).json()
    client.post("/api/v1/gym/sessions", json=session("c", "2026-11-26", exercises=("lat-pulldown",)))
    got = client.put("/api/v1/gym/sessions/c/note", json={"note": "Lat pulldown was too heavy"}).json()
    assert [a["kind"] for a in got["note_actions"]] == ["down"] and store.load().sessions[-1].note == "Lat pulldown was too heavy"
    a = got["note_actions"]
    assert client.post(f"/api/v1/gym/note-actions/{a[0]['id']}", json={"act": "dismiss"}).json()["actions"] == []
    assert client.put("/api/v1/gym/sessions/nope/note", json={"note": "x"}).status_code == 404


def test_the_model_may_only_name_this_workouts_exercises_and_the_five_areas():
    got = notes._valid([{"kind": "up", "exercise": "bench-press", "quote": "easy"}, {"kind": "up", "exercise": "made-up"},
                        {"kind": "spare", "area": "neck"}, {"kind": "spare", "area": "knee"}, {"kind": "delete", "exercise": "x"}], ENTRIES, "")
    assert [(a["kind"], a.get("exercise") or a.get("area")) for a in got] == [("up", "bench-press"), ("spare", "knee")]


def test_extras_are_tucked_away_by_default(client):
    assert client.get("/api/v1/gym").json()["settings"]["show_extras"] is False
