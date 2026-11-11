"""8.7: the SirisGym review: bad dates, unknown exercises, typo check data, set fixes, history links, tidy-up,
warm-ups, timed and bodyweight advice, recovery, the weekly push, lift goals and "how it felt"."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.gym import coach, service, store, tidy
from app.tasks import service as tasks
from tests.test_hub import AUTH

TODAY = date(2026, 11, 11)  # a Wednesday


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_GYM_PATH", str(tmp_path / "gym.json"))
    monkeypatch.setattr(tasks, "today", lambda: TODAY)
    return TestClient(app, headers=AUTH)


def session(sid: str, day: str, sets: list[tuple[float, int]], exercise: str = "bench-press", **extra) -> dict:
    return {"id": sid, "title": "Push", "started_at": f"{day}T07:00:00+11:00", "ended_at": f"{day}T08:00:00+11:00",
            "entries": [{"exercise": exercise, "sets": [{"weight": w, "reps": r} for w, r in sets]}], **extra}


def test_a_start_that_isnt_a_time_is_refused_and_an_old_one_set_aside(client, tmp_path):
    assert client.post("/api/v1/gym/sessions", json={**session("x", "2026-11-10", [(50, 5)]), "started_at": "not a date"}).status_code == 422
    assert client.post("/api/v1/gym/sessions", json=session("future", "2031-01-01", [(50, 5)])).status_code == 422
    back = client.post("/api/v1/gym/sessions", json={**session("y", "2026-11-10", [(50, 5)]), "ended_at": "2026-11-09T07:00:00+11:00"}).json()
    assert back["summary"]["minutes"] is None or back["summary"]["minutes"] >= 0, "an end before the start is dropped, never a negative length"
    # A file that already has one (from before 8.7): every page still loads, and the bad one is kept aside.
    raw = json.loads((tmp_path / "gym.json").read_text())
    raw["sessions"].append({"id": "bad", "title": "?", "started_at": "not a date", "entries": []})
    (tmp_path / "gym.json").write_text(json.dumps(raw))
    assert client.get("/api/v1/gym").status_code == 200
    assert client.get("/api/v1/gym/sessions").status_code == 200
    doc = store.load()
    assert [q["id"] for q in doc.quarantined] == ["bad"] and all(s.id != "bad" for s in doc.sessions)
    assert list(tmp_path.glob("gym.before-quarantine.*.json"))


def test_an_unknown_exercise_becomes_one_of_yours(client):
    client.post("/api/v1/gym/sessions", json=session("u", "2026-11-10", [(40, 8)], exercise="zercher-squat"))
    mine = next(e for e in client.get("/api/v1/gym").json()["exercises"] if e["id"] == "zercher-squat")
    assert mine["name"] == "Zercher Squat" and mine["custom"]


def test_the_typo_check_knows_your_recent_best_and_a_set_can_be_fixed(client):
    client.post("/api/v1/gym/sessions", json=session("a", "2026-10-01", [(90, 5), (90, 5)], exercise="back-squat"))
    client.post("/api/v1/gym/sessions", json=session("b", "2026-10-08", [(70, 8), (210, 8)], exercise="back-squat"))
    over = client.get("/api/v1/gym").json()
    assert over["recent_max"]["back-squat"] == 210
    assert client.put("/api/v1/gym/sessions/b/sets", json={"exercise": "back-squat", "sets": [{"weight": 70, "reps": 8}]}).status_code == 422
    fixed = client.put("/api/v1/gym/sessions/b/sets", json={"exercise": "back-squat", "sets": [{"weight": 70, "reps": 8}, {"weight": 72.5, "reps": 8}]})
    assert fixed.status_code == 200 and fixed.json()["summary"]["volume"] == 70 * 8 + 72.5 * 8
    assert client.get("/api/v1/gym").json()["recent_max"]["back-squat"] == 90


def test_the_routine_links_to_your_history(client):
    doc = store.load()
    mine = store.CustomExercise(name="Barbell Squat", primary="quads", equipment="barbell")
    doc.exercises.append(mine)
    doc.routines.append(store.Routine(name="R", active=True, days=[store.RoutineDay(name="Legs", exercises=[store.PlanExercise(exercise="back-squat")])]))
    store.save(doc)
    for i in range(6):
        client.post("/api/v1/gym/sessions", json=session(f"s{i}", f"2026-10-0{i + 1}", [(80, 8)], exercise=mine.id))
    links = client.get("/api/v1/gym/links").json()["links"]
    assert links[0]["exercise"] == "back-squat" and links[0]["options"][0]["id"] == mine.id
    r = client.post("/api/v1/gym/links", json={"source": "back-squat", "into": mine.id}).json()
    assert r["changed"] == 1 and r["links"] == []
    assert store.load().routines[0].days[0].exercises[0].exercise == mine.id
    plan = client.get(f"/api/v1/gym/plan?routine={store.load().routines[0].id}").json()["exercises"][0]
    assert plan["last"] and plan["suggest"]["weight"] == 80 and plan["best_e1rm"] and plan["recent_max"] == 80


def test_keep_as_is_stops_asking(client):
    doc = store.load()
    doc.routines.append(store.Routine(name="R", active=True, days=[store.RoutineDay(name="A", exercises=[store.PlanExercise(exercise="face-pull")])]))
    mine = store.CustomExercise(name="Cable Rope Face Pull", primary="shoulders", equipment="cable")
    doc.exercises.append(mine)
    store.save(doc)
    for i in range(5):
        client.post("/api/v1/gym/sessions", json=session(f"f{i}", f"2026-09-0{i + 1}", [(20, 12)], exercise=mine.id))
    assert client.get("/api/v1/gym/links").json()["links"]
    assert client.post("/api/v1/gym/links", json={"source": "face-pull", "keep": True}).json()["links"] == []


def test_duplicates_go_by_equipment_too():
    doc = store.GymDoc(exercises=[store.CustomExercise(name="Machine Bench Press", primary="chest", equipment="machine"),
                                  store.CustomExercise(name="Dumbbell Incline Bench Press", primary="chest", equipment="dumbbell"),
                                  store.CustomExercise(name="Barbell Up Right Row", primary="shoulders", equipment="barbell")])
    pairs = {(d["from_name"], d["into_name"]) for d in tidy.duplicates(doc)}
    assert ("Machine Bench Press", "Bench Press") not in pairs
    assert ("Dumbbell Incline Bench Press", "Incline Bench Press") not in pairs
    assert ("Barbell Up Right Row", "Upright Row") in pairs


def test_imported_exercises_get_a_tidy_up(client, tmp_path):
    doc = store.load()
    doc.exercises += [store.CustomExercise(name="Back Hyperextension", primary="triceps"), store.CustomExercise(name="Ab Crunch Machine", primary="abs", equipment="machine"),
                      store.CustomExercise(name="Machine Fly", primary="chest", equipment="machine"), store.CustomExercise(name="Plank Hold", primary="abs"),
                      store.CustomExercise(name="Weighted Pull-Up", primary="full body")]
    store.save(doc)
    fixes = {f["name"]: f["change"] for f in client.get("/api/v1/gym/exercise-fixes").json()["fixes"]}
    assert fixes["Back Hyperextension"] == {"kind": "bodyweight", "equipment": "bodyweight", "primary": "back"}
    assert "Ab Crunch Machine" not in fixes and "Machine Fly" not in fixes, "a loaded machine stays weighted; 'machine' isn't 'chin'"
    assert fixes["Plank Hold"]["kind"] == "time" and fixes["Weighted Pull-Up"] == {"primary": "back"}
    ids = {e.name: e.id for e in store.load().exercises}
    r = client.post("/api/v1/gym/exercise-fixes", json={"ids": [ids["Back Hyperextension"]]}).json()
    assert r["changed"] == 1 and list(tmp_path.glob("gym.before-exercise-fixes.*.json"))
    hyper = next(e for e in store.load().exercises if e.name == "Back Hyperextension")
    assert (hyper.kind, hyper.primary) == ("bodyweight", "back")
    client.post("/api/v1/gym/exercise-fixes", json={"ids": [ids["Plank Hold"]], "keep": True})
    assert "Plank Hold" not in {f["name"] for f in client.get("/api/v1/gym/exercise-fixes").json()["fixes"]}
    assert client.put(f"/api/v1/gym/exercises/{ids['Weighted Pull-Up']}", json={"primary": "back", "equipment": "bodyweight"}).json()["primary"] == "back"
    assert client.put(f"/api/v1/gym/exercises/{ids['Weighted Pull-Up']}", json={"primary": "elbows"}).status_code == 422


def test_warm_ups_only_for_barbell_lifts(client):
    doc = store.load()
    assert service.warmups(doc, "bench-press", 100)
    assert service.warmups(doc, "db-bench-press", 30) == []
    assert service.warmups(doc, "leg-press", 170) == []
    assert [w["weight"] for w in service.warmups(doc, "back-squat", 60)] == [20, 35, 47.5], "no 25 kg step right after the bar"


def test_timed_and_bodyweight_exercises_get_their_own_advice(client):
    client.post("/api/v1/gym/sessions", json={**session("p", "2026-11-01", []), "entries": [{"exercise": "plank", "sets": [{"seconds": 40}, {"seconds": 45}]},
                                                                                              {"exercise": "pull-up", "sets": [{"reps": 10}, {"reps": 8}]}]})
    doc = store.load()
    plank = service.suggest(doc, store.PlanExercise(exercise="plank", reps="30-60"))
    assert "45 s" in plank["why"] and "weight" not in plank["why"]
    pull = service.suggest(doc, store.PlanExercise(exercise="pull-up", reps="10-15"))
    assert "10, 8 reps" in pull["why"]


def test_deload_not_now_and_targets_through_the_week(client):
    doc = store.load()
    assert coach.deload(doc, TODAY)["suggest"] is False
    client.post("/api/v1/gym/deload", json={"later": True})
    assert store.load().settings.deload_snoozed_until == "2026-12-08"
    client.post("/api/v1/gym/sessions", json=session("m", "2026-11-10", [(60, 8)] * 5))  # Tuesday: 5 chest sets, on track by Wednesday
    wed = {m["muscle"]: m["status"] for m in coach.muscles(store.load(), TODAY)}
    sun = {m["muscle"]: m["status"] for m in coach.muscles(store.load(), date(2026, 11, 15))}
    assert wed["chest"] == "in range" and sun["chest"] == "under"


def test_recovery_and_the_weekly_message(client):
    client.post("/api/v1/gym/sessions", json=session("r", "2026-11-10", [(60, 8)] * 3))
    rec = {r["muscle"]: r for r in coach.recovery(store.load(), datetime(2026, 11, 11, 7, tzinfo=timezone.utc))}
    assert rec["chest"]["hours"] is not None and 0 < rec["chest"]["ready"] < 100 and rec["quads"]["ready"] is None
    msg = coach.weekly_message(store.load(), date(2026, 11, 15))
    assert msg["title"].startswith("Your gym week: 1 workout")


def test_how_it_felt_and_against_last_time(client):
    client.post("/api/v1/gym/sessions", json=session("one", "2026-11-03", [(60, 8)] * 3))
    r = client.post("/api/v1/gym/sessions", json=session("two", "2026-11-10", [(60, 8)] * 4)).json()
    assert r["compare"]["sets"] == 1 and r["compare"]["volume"] == 480
    assert client.post("/api/v1/gym/sessions/two/feel", json={"feel": 4}).json()["feel"] == 4
    assert client.post("/api/v1/gym/sessions/two/feel", json={"feel": 9}).status_code == 422
    again = client.post("/api/v1/gym/sessions", json=session("two", "2026-11-10", [(60, 8)] * 4))  # re-sent from the phone: the feel stays
    assert again.json()["summary"]["feel"] == 4


def test_a_lift_goal_counts_your_best_this_year(client, monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_GOALS_PATH", str(tmp_path / "goals.json"))
    client.post("/api/v1/gym/sessions", json=session("g", "2026-03-01", [(100, 5)]))
    assert client.post("/api/v1/goals?year=2026", json={"title": "Bench 120", "kind": "lift", "target": 120}).status_code == 422
    client.post("/api/v1/goals?year=2026", json={"title": "Bench 120", "kind": "lift", "target": 120, "exercise": "bench-press"})
    g = client.get("/api/v1/goals?year=2026").json()["goals"][0]
    assert g["value"] == 116.7 and g["unit"] == "kg" and g["source"] == "SirisGym"
