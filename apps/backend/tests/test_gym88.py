"""8.8: Siri logging, planned lighter weeks, trends by muscle, how you are today, set types, bodyweight volume,
form cues, the monthly reminder, backup retention, the next block and gym swaps."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.gym import coach, service, store, voice
from app.push import notifier
from app.tasks import service as tasks
from tests.test_hub import AUTH

TODAY = date(2026, 11, 12)  # a Thursday


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_GYM_PATH", str(tmp_path / "gym.json"))
    monkeypatch.setenv("SIRISOS_GYM_VOICE_PATH", str(tmp_path / "gym-voice.json"))
    monkeypatch.setattr(tasks, "today", lambda: TODAY)
    return TestClient(app, headers=AUTH)


def session(sid: str, day: str, sets: list[tuple[float | None, int]], exercise: str = "bench-press", **extra) -> dict:
    return {"id": sid, "title": "Push", "started_at": f"{day}T07:00:00+11:00", "ended_at": f"{day}T08:00:00+11:00",
            "entries": [{"exercise": exercise, "sets": [{"weight": w, "reps": r} for w, r in sets]}], **extra}


def routine(*exercises: str, **extra) -> store.Routine:
    return store.Routine(name="R", active=True, days=[store.RoutineDay(name="A", exercises=[store.PlanExercise(exercise=e, reps="6-10") for e in exercises])], **extra)


def test_siri_logs_a_set_with_its_key_and_nothing_else(client):
    bare = TestClient(app)
    assert bare.post("/api/v1/gym-voice/log", json={"text": "100 by 5"}).status_code == 401
    key = client.post("/api/v1/gym/voice-key").json()["key"]
    assert store.load().settings.voice_key_hash and key not in store.load().model_dump_json(), "only the hash is kept"
    r = bare.post("/api/v1/gym-voice/log", json={"text": "bench 82.5 for 8"}, headers={"X-SirisGym-Key": key})
    assert r.status_code == 200 and r.json()["say"].startswith("Got it: 82.5 by 8 for bench")
    assert bare.post("/api/v1/gym-voice/log", json={"text": "hello"}, headers={"X-SirisGym-Key": key}).status_code == 422
    assert bare.post("/api/v1/gym-voice/log", json={"text": "100 by 5"}, headers={"X-SirisGym-Key": "sg_wrong"}).status_code == 401
    assert bare.get("/api/v1/gym/voice-log").status_code == 401, "reading the queue needs the sign-in"
    items = client.get("/api/v1/gym/voice-log").json()["items"]
    assert items[0]["parsed"] == {"weight": 82.5, "reps": 8, "name": "bench"}
    assert client.post("/api/v1/gym/voice-log/ack", json={"ids": [items[0]["id"]]}).json()["taken"] == 1
    client.delete("/api/v1/gym/voice-key")
    assert bare.post("/api/v1/gym-voice/log", json={"text": "100 by 5"}, headers={"X-SirisGym-Key": key}).status_code == 401


def test_the_parser_understands_spoken_sets():
    assert voice.parse("one hundred by five") == {"weight": 100.0, "reps": 5}
    assert voice.parse("sixty two point five for eight rpe 8") == {"weight": 62.5, "reps": 8, "rpe": 8.0}
    assert voice.parse("bodyweight 12") == {"weight": None, "reps": 12}
    assert voice.parse("good morning") is None


def test_a_planned_lighter_week(client):
    doc = store.load()
    doc.routines.append(routine("bench-press", deload_every=4, block_started="2026-10-19"))  # weeks: 19 Oct, 26 Oct, 2 Nov, 9 Nov (the 4th)
    store.save(doc)
    d = coach.deload(store.load(), TODAY)
    assert d["active"] and d["planned"]["this_week"] and d["until"] == "2026-11-15"
    nxt = coach.deload(store.load(), date(2026, 11, 17))
    assert not nxt["active"] and not nxt["suggest"] and nxt["planned"]["in_weeks"] == 3


def test_tired_and_short_on_time(client):
    doc = store.load()
    doc.routines.append(routine("bench-press", "barbell-row", "overhead-press", "pull-up", "db-curl"))
    store.save(doc)
    client.post("/api/v1/gym/sessions", json=session("b", "2026-11-05", [(100, 10)] * 3))
    rid = store.load().routines[0].id
    normal = client.get(f"/api/v1/gym/plan?routine={rid}").json()
    tired = client.get(f"/api/v1/gym/plan?routine={rid}&mode=tired").json()
    short = client.get(f"/api/v1/gym/plan?routine={rid}&mode=short").json()
    assert tired["exercises"][0]["sets"] == normal["exercises"][0]["sets"] - 1 and tired["exercises"][0]["suggest"]["why"].startswith("You're tired today")
    assert len(short["exercises"]) == 3 and short["mode_note"] == "Short on time: the first 3 of 5 exercises."


def test_trends_by_muscle(client):
    for i, day in enumerate(["2026-05-04", "2026-06-04", "2026-07-04", "2026-08-04", "2026-09-04", "2026-10-04", "2026-11-04"]):
        client.post("/api/v1/gym/sessions", json=session(f"t{i}", day, [(60, 8)] * (3 if i < 4 else 6)))
    t = client.get("/api/v1/gym/muscle-trends?months=12").json()
    chest = next(m for m in t["muscles"] if m["muscle"] == "chest")
    assert t["months"][-1] == "2026-11" and chest["series"][-1] == 6 and chest["change"] == 67  # Aug-Oct against May-Jul: this month is only part done
    assert next(m for m in t["muscles"] if m["muscle"] == "triceps")["series"][-1] == 3, "a helper counts half"


def test_new_set_types_count_as_working_sets():
    s = store.SetLog(weight=60, reps=12, type="amrap")
    assert service.working([s, store.SetLog(weight=40, reps=5, type="warmup"), store.SetLog(weight=50, reps=20, type="restpause")]) != []
    assert len(service.working([s, store.SetLog(weight=50, reps=20, type="restpause")])) == 2


def test_bodyweight_exercises_count_your_bodyweight(client):
    doc = store.load()
    doc.settings.bodyweight_kg = 77
    store.save(doc)
    r = client.post("/api/v1/gym/sessions", json={**session("p", "2026-11-11", []), "entries": [{"exercise": "pull-up", "sets": [{"reps": 10}, {"weight": 10, "reps": 8}]}]})
    assert r.json()["summary"]["volume"] == 77 * 10 + 87 * 8


def test_form_cues(client):
    d = client.get("/api/v1/gym/exercises/back-squat").json()
    assert "knees out" in d["cues"] and not d["cues_yours"]
    client.put("/api/v1/gym/exercises/back-squat/cues", json={"text": "Belt on · wide stance"})
    assert client.get("/api/v1/gym/exercises/back-squat").json()["cues"] == "Belt on · wide stance"
    doc = store.load()
    doc.routines.append(routine("back-squat"))
    store.save(doc)
    plan = client.get(f"/api/v1/gym/plan?routine={store.load().routines[0].id}").json()
    assert plan["exercises"][0]["cues"] == "Belt on · wide stance"
    client.put("/api/v1/gym/exercises/back-squat/cues", json={"text": ""})
    assert "knees out" in client.get("/api/v1/gym/exercises/back-squat").json()["cues"]


def test_the_monthly_measurements_reminder(client):
    client.post("/api/v1/gym/sessions", json=session("m", "2026-11-05", [(60, 8)]))
    assert notifier.gym_measure_message(datetime(2026, 12, 1, 9, 30))[0]["key"] == "gym:measure:2026-12"
    assert notifier.gym_measure_message(datetime(2026, 12, 2, 9, 30)) == []
    client.post("/api/v1/gym/measurements", json={"date": "2026-12-01", "waist": 84})
    assert notifier.gym_measure_message(datetime(2026, 12, 1, 10, 0)) == []


def test_old_backups_are_pruned(client, tmp_path):
    store.save(store.GymDoc())
    now = datetime(2026, 11, 12, tzinfo=timezone.utc)
    for i in range(14):
        when = now - timedelta(days=40 + i)
        (tmp_path / f"gym.before-test.{when.strftime('%Y%m%d-%H%M%S')}.json").write_text("{}")
    for i in range(3):
        (tmp_path / f"gym.recent.{(now - timedelta(days=i)).strftime('%Y%m%d-%H%M%S')}.json").write_text("{}")
    gone = store.prune_backups(now)
    assert len(gone) == 7 and len(list(tmp_path.glob("gym.*.*.json"))) == 10, "the newest 10 stay"


def test_the_next_block(client, tmp_path):
    doc = store.load()
    doc.routines.append(routine("bench-press", "back-squat", "overhead-press", block_started="2026-09-21"))
    store.save(doc)
    for i, (b, sq) in enumerate([(100, 80), (100, 85), (100, 90), (100, 95)]):
        client.post("/api/v1/gym/sessions", json={**session(f"x{i}", f"2026-10-{5 + i * 7:02d}", []), "entries": [
            {"exercise": "bench-press", "sets": [{"weight": b, "reps": 8}]}, {"exercise": "back-squat", "sets": [{"weight": sq, "reps": 8}]}]})
    client.post("/api/v1/gym/sessions", json=session("db", "2026-08-01", [(30, 10)], exercise="db-bench-press"))
    block = client.get("/api/v1/gym/next-block").json()["block"]
    assert block["due"] and block["weeks"] == 7
    verdicts = {c["exercise"]: c for c in block["changes"]}
    assert verdicts["back-squat"]["verdict"] == "keep" and verdicts["overhead-press"]["verdict"] == "keep"
    assert verdicts["bench-press"]["verdict"] == "swap" and verdicts["bench-press"]["swap_to"] == "db-bench-press"
    i = block["changes"].index(verdicts["bench-press"])
    assert client.post("/api/v1/gym/next-block", json={"accept": [i]}).json()["changed"] == 1
    r = store.load().routines[0]
    assert r.days[0].exercises[0].exercise == "db-bench-press" and r.block_started == TODAY.isoformat()
    assert list(tmp_path.glob("gym.before-block.*.json"))


def test_a_gym_remembers_its_swaps(client):
    doc = store.load()
    doc.settings.gyms = [store.GymProfile(id="home", name="Home"), store.GymProfile(id="work", name="Work gym")]
    doc.routines.append(routine("back-squat"))
    store.save(doc)
    assert client.post("/api/v1/gym/gyms/work/swaps", json={"source": "back-squat", "into": "leg-press"}).json()["swaps"] == {"back-squat": "leg-press"}
    rid = store.load().routines[0].id
    at_work = client.get(f"/api/v1/gym/plan?routine={rid}&gym=work").json()["exercises"][0]
    at_home = client.get(f"/api/v1/gym/plan?routine={rid}&gym=home").json()["exercises"][0]
    assert at_work["exercise"] == "leg-press" and at_work["gym_swap"] == {"from": "back-squat", "gym": "Work gym"}
    assert at_home["exercise"] == "back-squat"
    client.post("/api/v1/gym/gyms/work/swaps", json={"source": "back-squat"})
    assert client.get(f"/api/v1/gym/plan?routine={rid}&gym=work").json()["exercises"][0]["exercise"] == "back-squat"



def test_saving_settings_from_the_phone_keeps_the_siri_key(client):
    client.post("/api/v1/gym/voice-key")
    s = client.get("/api/v1/gym").json()["settings"]
    assert "voice_key_hash" not in s and s["voice_key"] is True
    s.pop("voice_key")
    assert client.put("/api/v1/gym/settings", json={**s, "rest_s": 100}).json()["voice_key"] is True
    assert store.load().settings.voice_key_hash


def test_a_tired_day_never_adds_weight(client):
    """Last time every set reached the top of the range, so the plan adds weight; tired, it's 5% off that, and never over last time."""
    client.post("/api/v1/gym/routines", json={"routine": {"name": "R", "active": True, "days": [{"name": "A", "exercises": [{"exercise": "bench-press", "sets": 3, "reps": "6-10"}]}]}})
    client.post("/api/v1/gym/sessions", json=session("x", "2026-11-05", [(100, 10)] * 3))
    rid = next(r.id for r in store.load().routines if r.name == "R")
    normal = client.get(f"/api/v1/gym/plan?routine={rid}").json()["exercises"][0]["suggest"]["weight"]
    tired = client.get(f"/api/v1/gym/plan?routine={rid}&mode=tired").json()["exercises"][0]["suggest"]["weight"]
    assert normal > 100 and tired < 100
    # a big step on a light dumbbell: 5% off the plan would still be over last time, so it's 5% off last time
    client.post("/api/v1/gym/routines", json={"routine": {"name": "D", "active": True, "days": [{"name": "A", "exercises": [{"exercise": "dumbbell-curl", "sets": 3, "reps": "6-10"}]}]}})
    client.post("/api/v1/gym/sessions", json=session("y", "2026-11-06", [(10, 10)] * 3, exercise="dumbbell-curl"))
    did = next(r.id for r in store.load().routines if r.name == "D")
    curl = client.get(f"/api/v1/gym/plan?routine={did}&mode=tired").json()["exercises"][0]["suggest"]["weight"]
    assert curl < 10
