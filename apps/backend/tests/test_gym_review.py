"""Imports that can't be one workout, duplicate exercises, and what's sent where (7.0)."""

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.gym import api as gym_api, importer, service, store, tidy
from app.hub import service as hub_service
from tests.test_hub import AUTH


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_GYM_PATH", str(tmp_path / "gym.json"))
    monkeypatch.setattr(gym_api, "_health_saved", None)
    return TestClient(app, headers=AUTH)


def imported(day: str, n: int, weight: float = 50, reps: int = 8, exercise: str = "bench-press") -> store.Session:
    return store.Session(id=f"import-{day.replace('-', '')}", title="Chest", started_at=f"{day}T07:00:00",
                         entries=[store.EntryLog(exercise=exercise, sets=[store.SetLog(weight=weight, reps=reps) for _ in range(n)])])


def saved(*sessions: store.Session, **kw) -> store.GymDoc:
    doc = store.GymDoc(sessions=list(sessions), **kw)
    store.save(doc)
    return doc


def test_a_day_with_too_many_sets_or_tonnes_is_held_and_a_real_one_isnt():
    assert store.held(imported("2025-02-25", 61))
    assert store.held(imported("2025-02-26", 40, weight=200, reps=10))  # 80 tonnes
    assert not store.held(imported("2025-02-27", 20))
    live = imported("2025-02-28", 100)
    live.id = "s1"
    assert not store.held(live)  # one you logged yourself is what you did


def test_a_held_day_counts_for_nothing_until_you_say_its_real(client):
    saved(imported("2026-10-01", 10, weight=60), imported("2026-10-02", 500, weight=300, reps=1))
    doc = store.load()
    assert len(doc.sessions) == 2, "nothing is removed"
    assert max(r["best"]["weight"] for r in service.history(doc, "bench-press")) == 60
    assert client.get("/api/v1/gym").json()["held"][0]["id"] == "import-20261002"
    assert client.get("/api/v1/gym").json()["total_sessions"] == 1

    r = client.post("/api/v1/gym/sessions/import-20261002/review", json={"verdict": "real"})
    assert r.json()["left"] == 0
    assert max(x["best"]["weight"] for x in service.history(store.load(), "bench-press")) == 300
    assert client.get("/api/v1/gym").json()["held"] == []

    client.post("/api/v1/gym/sessions/import-20261002/review", json={"verdict": "wrong"})
    doc = store.load()
    assert max(x["best"]["weight"] for x in service.history(doc, "bench-press")) == 60
    assert client.get("/api/v1/gym").json()["held"] == [], "you've looked: it doesn't ask again"
    assert len(doc.sessions) == 2 and sum(len(e.sets) for e in doc.sessions[1].entries) == 500, "still all there"


def test_an_import_keeps_every_set_and_your_verdict(client):
    rows = [{"date": importer.parse_date("2026-09-01"), "exercise": "Bench Press", "weight": 50.0, "reps": 5, "order": (0, i)} for i in range(120)]
    doc = store.load()
    importer.commit(doc, rows, {})
    doc = store.load()
    assert sum(len(e.sets) for e in doc.sessions[0].entries) == 120
    assert doc.sessions[0].title == "Chest"
    doc.sessions[0].review = "real"
    store.save(doc)
    importer.commit(store.load(), rows, {})
    assert store.load().sessions[0].review == "real"


def test_old_imports_get_their_names_once_with_a_copy_first(client, tmp_path):
    bench, row = imported("2026-09-01", 4), imported("2026-09-01", 4, exercise="barbell-row")
    bench.entries += row.entries
    bench.title = store.IMPORTED
    raw = store.GymDoc(sessions=[bench]).model_dump()
    del raw["import_titles"]
    (tmp_path / "gym.json").write_text(json.dumps(raw))
    assert store.load().sessions[0].title == "Chest and Back"
    assert list(tmp_path.glob("gym.before-titles.*.json"))
    assert json.loads((tmp_path / "gym.json").read_text())["import_titles"] is True


def test_a_name_follows_the_muscles_that_got_the_work():
    doc = store.GymDoc()
    one = [store.EntryLog(exercise="bench-press", sets=[store.SetLog(weight=50, reps=5)] * 9),
           store.EntryLog(exercise="barbell-row", sets=[store.SetLog(weight=50, reps=5)])]
    assert service.trained_title(doc, one) == "Chest"
    assert service.trained_title(doc, []) == "Workout"


def mine(name: str, kind: str = "weight") -> store.CustomExercise:
    return store.CustomExercise(name=name, primary="back", kind=kind)


def test_same_names_are_paired_but_different_kit_isnt():
    a, b = mine("Cable V Bar Pull Down"), mine("Cable V Bar Pulldown")
    c, d = mine("Zottman Barbell Twist"), mine("Zottman Dumbbell Twist")
    e, f = mine("Hack Lat Thing"), mine("Machine Hack Lat Things")
    doc = store.GymDoc(exercises=[a, b, c, d, e, f], sessions=[imported("2026-01-01", 5, exercise=b.id)])
    found = {(x["from"], x["into"]): x for x in tidy.duplicates(doc)}
    assert (a.id, b.id) in found and found[(a.id, b.id)]["sure"]
    assert not any({x["from_name"], x["into_name"]} == {c.name, d.name} for x in found.values())
    assert any({x["from_name"], x["into_name"]} == {e.name, f.name} and not x["sure"] for x in found.values())


def test_merging_moves_every_set_and_follows_routines(client, tmp_path):
    a, b = mine("Seated Tricep Press"), mine("Seated Triceps Press")
    both = imported("2026-01-01", 3, exercise=a.id)
    both.entries.append(store.EntryLog(exercise=b.id, sets=[store.SetLog(weight=10, reps=5)] * 2))
    only = imported("2026-01-02", 4, exercise=a.id)
    routine = store.Routine(name="R", days=[store.RoutineDay(name="D", exercises=[store.PlanExercise(exercise=a.id)])])
    saved(both, only, exercises=[a, b], routines=[routine])

    r = client.post("/api/v1/gym/merge", json={"source": a.id, "into": b.id})
    assert r.status_code == 200 and r.json()["sets_moved"] == 7 and r.json()["workouts"] == 2
    doc = store.load()
    assert [e.id for e in doc.exercises] == [b.id]
    assert [(len(s.entries), sum(len(e.sets) for e in s.entries)) for s in doc.sessions] == [(1, 5), (1, 4)]
    assert all(e.exercise == b.id for s in doc.sessions for e in s.entries)
    assert doc.routines[0].days[0].exercises[0].exercise == b.id
    assert list(tmp_path.glob("gym.before-merge.*.json"))


def test_a_built_in_cant_be_merged_away(client):
    assert client.post("/api/v1/gym/merge", json={"source": "bench-press", "into": "barbell-row"}).status_code == 422


def test_test_mode_lets_reads_through_and_stops_writes(monkeypatch):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.method)
        return httpx.Response(200, json={})

    monkeypatch.setenv("SIRISOS_TEST_MODE", "1")
    async def go() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), event_hooks={"request": [hub_service._test_mode_guard]}) as c:
            await c.get("http://sirisai:8000/siris/status")
            with pytest.raises(httpx.HTTPError):
                await c.post("http://sirisai:8000/siris/health/gym", json={})
            await c.post("http://localhost:8000/here", json={})

    asyncio.run(go())
    assert seen == ["GET", "POST"]
    monkeypatch.delenv("SIRISOS_TEST_MODE")
    assert not hub_service.test_mode()


def test_a_stall_is_recent_not_against_a_best_from_years_ago():
    from datetime import date

    from app.gym import coach

    def bench(day: str, weight: float) -> store.Session:
        s = imported(day, 3, weight=weight, reps=5)
        s.id = f"s{day}"
        return s

    today = date(2026, 11, 5)
    old_best = [bench("2022-01-01", 200)]
    climbing = [bench(f"2026-10-{d:02d}", 60 + d) for d in range(1, 10)]
    assert coach._stalled(store.GymDoc(sessions=old_best + climbing), today) == []
    flat = [bench(f"2026-10-{d:02d}", 100) for d in range(1, 10)]
    assert coach._stalled(store.GymDoc(sessions=flat), today) == ["Bench Press"]
    assert coach._stalled(store.GymDoc(sessions=flat), date(2027, 6, 1)) == [], "a lift you've stopped doing isn't stalled"


def test_a_merge_can_be_undone_and_the_pair_isnt_suggested_again(client):
    a, b = mine("Seated Tricep Press"), mine("Seated Triceps Press")
    both = imported("2026-01-01", 3, exercise=b.id)
    both.entries.insert(0, store.EntryLog(exercise=a.id, sets=[store.SetLog(weight=10, reps=5)] * 2, note="mine"))
    only = imported("2026-01-02", 4, exercise=a.id)
    untouched = imported("2026-01-03", 2, exercise=b.id)
    routine = store.Routine(name="R", days=[store.RoutineDay(name="D", exercises=[store.PlanExercise(exercise=a.id)])])
    saved(both, only, untouched, exercises=[a, b], routines=[routine])
    assert client.post("/api/v1/gym/merge", json={"source": a.id, "into": b.id}).status_code == 200

    merges = client.get("/api/v1/gym/merges").json()["merges"]
    assert [(m["from_name"], m["into_name"], m["sets_moved"], m["workouts"]) for m in merges] == [("Seated Tricep Press", "Seated Triceps Press", 6, 2)]
    r = client.post(f"/api/v1/gym/merges/{merges[0]['id']}/undo")
    assert r.status_code == 200 and r.json()["sets_back"] == 6
    doc = store.load()
    assert {e.id for e in doc.exercises} == {a.id, b.id}
    assert [[(e.exercise, len(e.sets)) for e in s.entries] for s in doc.sessions] == [[(a.id, 2), (b.id, 3)], [(a.id, 4)], [(b.id, 2)]]
    assert doc.sessions[0].entries[0].note == "mine"
    assert doc.routines[0].days[0].exercises[0].exercise == a.id
    assert client.get("/api/v1/gym/merges").json()["merges"] == []
    assert client.get("/api/v1/gym/duplicates").json()["duplicates"] == []  # undone means they're not the same
    assert client.post(f"/api/v1/gym/merges/{merges[0]['id']}/undo").status_code == 404


def test_a_pair_you_say_isnt_the_same_isnt_suggested_again(client):
    a, b = mine("Cable V Bar Pull Down"), mine("Cable V Bar Pulldown")
    saved(imported("2026-01-01", 5, exercise=b.id), exercises=[a, b])
    found = client.get("/api/v1/gym/duplicates").json()["duplicates"]
    assert len(found) == 1
    r = client.post("/api/v1/gym/duplicates/dismiss", json={"source": found[0]["from"], "into": found[0]["into"]})
    assert r.status_code == 200 and r.json()["duplicates"] == []
    assert store.load().not_duplicates == [[a.id, b.id]]


def test_a_workout_saved_while_sirisai_is_down_goes_when_its_back(client, monkeypatch):
    up = {"ok": False}
    sent: list[str] = []

    async def fake_post(hub, path, **kw):
        if not up["ok"]:
            raise RuntimeError("SirisAI unreachable")
        sent.append(path)
        return {}

    monkeypatch.setattr(gym_api.sirisai_api, "post", fake_post)
    body = {"id": "w1", "title": "Push", "started_at": "2026-11-10T07:00:00+00:00", "ended_at": "2026-11-10T08:00:00+00:00", "entries": [
        {"exercise": "bench-press", "sets": [{"weight": 80, "reps": 8, "done": True, "at": "2026-11-10T07:05:00"}]}]}
    r = client.post("/api/v1/gym/sessions", json=body)
    assert r.status_code == 200 and r.json()["ai_pending"] is True
    assert store.load().sessions[0].ai_pending

    hub = object()
    assert asyncio.run(gym_api.resend_pending(hub)) == 0  # still down: kept for later
    up["ok"] = True
    assert asyncio.run(gym_api.resend_pending(hub)) == 1
    assert "/siris/health/gym/session" in sent and not store.load().sessions[0].ai_pending
    assert asyncio.run(gym_api.resend_pending(hub)) == 0  # nothing left
