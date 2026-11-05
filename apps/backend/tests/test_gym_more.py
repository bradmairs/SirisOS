"""7.1: the Watch steers what to lift and the rest, fitter at the same weight, niggles, cardio, form videos, backups and export."""

from __future__ import annotations

import csv
import io
import json

from app.gym import store, watch
from tests.test_gym import AUTH, client, health, session  # noqa: F401 - fixtures


def _routine(client, exercises):  # noqa: F811
    body = {"routine": {"name": "Test", "active": True, "days": [{"name": "A", "exercises": exercises}]}}
    return client.post("/api/v1/gym/routines", headers=AUTH, json=body).json()["id"]


def _with_effort(client, sid, day, sets, effort, exercise="bench-press"):  # noqa: F811
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session(sid, day, sets, exercise))
    doc = store.load()
    s = next(x for x in doc.sessions if x.id == sid)
    s.effort = {exercise: effort}
    store.save(doc)


def test_an_easy_session_on_the_watch_adds_more_and_a_hard_one_holds(client, health):  # noqa: F811
    rid = _routine(client, [{"exercise": "bench-press", "sets": 3, "reps": "6-8", "rest_s": 90}])
    _with_effort(client, "s1", "2026-11-02", [(80, 8)] * 3, {"effort": 4.0, "peak_hr": 120, "recovery_bpm": 25})
    sug = client.get(f"/api/v1/gym/plan?routine={rid}", headers=AUTH).json()["exercises"][0]["suggest"]
    assert sug["weight"] == 85 and "barely rose" in sug["why"] and sug["watch_effort"] == 4.0
    _with_effort(client, "s1", "2026-11-02", [(80, 8)] * 3, {"effort": 9.0, "peak_hr": 175, "recovery_bpm": 8})
    sug = client.get(f"/api/v1/gym/plan?routine={rid}", headers=AUTH).json()["exercises"][0]["suggest"]
    assert sug["weight"] == 80 and "near your max" in sug["why"]
    _with_effort(client, "s1", "2026-11-02", [(80, 6)] * 3, {"effort": 9.0, "peak_hr": 175, "recovery_bpm": 30})
    sug = client.get(f"/api/v1/gym/plan?routine={rid}", headers=AUTH).json()["exercises"][0]["suggest"]
    assert sug["weight"] == 80 and "grind" in sug["why"]


def test_saving_a_session_again_keeps_the_watch_verdict(client, health):  # noqa: F811
    _with_effort(client, "s1", "2026-11-02", [(80, 8)], {"effort": 6.0})
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("s1", "2026-11-02", [(80, 8)]))
    assert store.load().sessions[0].effort == {"bench-press": {"effort": 6.0}}


def test_the_rest_timer_learns_from_how_long_heart_rate_takes_to_settle(client, health):  # noqa: F811
    rid = _routine(client, [{"exercise": "bench-press", "sets": 3, "reps": "6-8", "rest_s": 90}])
    for i, settle in enumerate((150, 170, 160)):
        _with_effort(client, f"s{i}", f"2026-11-0{i + 1}", [(80, 8)], {"effort": 7.0, "settle_s": settle})
    e = client.get(f"/api/v1/gym/plan?routine={rid}", headers=AUTH).json()["exercises"][0]
    assert e["rest_s"] == 165 and e["rest_learned"]["planned"] == 90 and "160 s" in e["rest_learned"]["why"]
    s = client.get("/api/v1/gym", headers=AUTH).json()["settings"]
    client.put("/api/v1/gym/settings", headers=AUTH, json={**s, "learn_rest": False})
    e = client.get(f"/api/v1/gym/plan?routine={rid}", headers=AUTH).json()["exercises"][0]
    assert e["rest_s"] == 90 and "rest_learned" not in e


def test_fitter_at_the_same_weight(client, health):  # noqa: F811
    _with_effort(client, "s1", "2026-10-01", [(80, 8)], {"effort": 7.0, "peak_hr": 150})
    _with_effort(client, "s2", "2026-10-20", [(80, 8)], {"effort": 6.0, "peak_hr": 145})
    _with_effort(client, "s3", "2026-11-02", [(80, 8)], {"effort": 5.0, "peak_hr": 139})
    f = client.get("/api/v1/gym/exercises/bench-press", headers=AUTH).json()["fitness"]
    assert f["verdict"] == "fitter" and f["delta_bpm"] == -11 and f["times"] == 3 and "11 bpm lower" in f["text"]
    from app.gym import coach
    assert "Bench Press" in coach.for_sirisai(store.load(), __import__("datetime").date(2026, 11, 4))["same_weight"][0]


def test_a_niggle_swaps_out_what_loads_it_until_its_healed(client, health):  # noqa: F811
    rid = _routine(client, [{"exercise": "back-squat", "sets": 3, "reps": "5", "rest_s": 120},
                            {"exercise": "bench-press", "sets": 3, "reps": "8", "rest_s": 90}])
    n = client.post("/api/v1/gym/niggles", headers=AUTH, json={"area": "knee", "note": "sore after running"}).json()
    plan = client.get(f"/api/v1/gym/plan?routine={rid}", headers=AUTH).json()["exercises"]
    assert plan[0]["exercise"] != "back-squat" and plan[0]["niggle"]["from"] == "back-squat" and "knee" in plan[0]["niggle"]["why"]
    assert not watch.fitness(store.load(), "back-squat")
    assert plan[1]["exercise"] == "bench-press" and "niggle" not in plan[1]
    assert client.get("/api/v1/gym", headers=AUTH).json()["niggles"][0]["area"] == "knee"
    client.post(f"/api/v1/gym/niggles/{n['id']}/healed", headers=AUTH)
    plan = client.get(f"/api/v1/gym/plan?routine={rid}", headers=AUTH).json()["exercises"]
    assert plan[0]["exercise"] == "back-squat" and client.get("/api/v1/gym", headers=AUTH).json()["niggles"] == []


def test_cardio_counts_in_the_week(client, health):  # noqa: F811
    s = session("c1", "2026-11-03", [], "rowing-machine")
    s["entries"][0]["sets"] = [{"seconds": 1200, "km": 4.8}]
    s["entries"].append({"exercise": "air-bike", "sets": [{"seconds": 600}]})
    client.post("/api/v1/gym/sessions", headers=AUTH, json=s)
    w = client.get("/api/v1/gym", headers=AUTH).json()["week"]
    assert w["cardio_min"] == 30 and w["cardio_km"] == 4.8 and w["cardio_sessions"] == 1


def test_form_videos_upload_list_play_and_delete(client, health):  # noqa: F811
    r = client.post("/api/v1/gym/videos", headers=AUTH, files={"file": ("squat.mp4", b"\x00" * 2048, "video/mp4")},
                    data={"exercise": "back-squat", "session": "s1", "set": "2", "weight": "100", "reps": "5"}).json()
    assert r["exercise"] == "back-squat" and r["set"] == 2 and "file" not in r
    assert client.post("/api/v1/gym/videos", headers=AUTH, files={"file": ("x.txt", b"hi", "text/plain")}, data={"exercise": "back-squat"}).status_code == 415
    got = client.get(f"/api/v1/gym/videos/{r['id']}", headers={**AUTH, "Range": "bytes=0-99"})
    assert got.status_code == 206 and len(got.content) == 100
    assert client.get("/api/v1/gym/exercises/back-squat", headers=AUTH).json()["videos"][0]["id"] == r["id"]
    client.delete(f"/api/v1/gym/videos/{r['id']}", headers=AUTH)
    assert client.get("/api/v1/gym/videos", headers=AUTH).json()["videos"] == []


def test_backups_restore_and_export(client, health, tmp_path):  # noqa: F811
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("s1", "2026-11-02", [(80, 8)]))
    name = store.backup("before-test")
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("s2", "2026-11-03", [(82.5, 8)]))
    b = client.get("/api/v1/gym/backups", headers=AUTH).json()["backups"]
    assert b[0]["name"] == name and b[0]["tag"] == "before-test" and b[0]["sessions"] == 1
    assert client.post("/api/v1/gym/backups/restore", headers=AUTH, json={"name": "../gym.json"}).status_code == 404
    r = client.post("/api/v1/gym/backups/restore", headers=AUTH, json={"name": name}).json()
    assert r["sessions"] == 1 and r["saved_current_as"].startswith("gym.before-restore.")
    assert [s.id for s in store.load().sessions] == ["s1"]
    assert json.loads((tmp_path / r["saved_current_as"]).read_text())["sessions"][1]["id"] == "s2"  # the restore can be undone
    rows = list(csv.DictReader(io.StringIO(client.get("/api/v1/gym/export.csv", headers=AUTH).text)))
    assert rows[1]["exercise"] == "Bench Press" and rows[1]["weight_kg"] == "80.0" and rows[0]["type"] == "warmup"
    assert client.get("/api/v1/gym/export.json", headers=AUTH).json()["sessions"][0]["id"] == "s1"


def test_recent_workouts_get_the_watch_verdict_when_planning(client, health, monkeypatch):  # noqa: F811
    from app.gym import api as gym_api
    from app.hub import sirisai_api

    async def get(hub, path, params=None, timeout=20.0):
        return {"linked": True, "exercises": [{"id": "bench-press", "exercise": "Bench Press", "effort": 4.5, "peak_hr": 130, "settle_s": 75}]}

    async def post(hub, path, json=None, headers=None, timeout=20.0, **kw):
        return {}

    monkeypatch.setattr(sirisai_api, "get", get)
    monkeypatch.setattr(sirisai_api, "post", post)
    gym_api._TRIED.clear()
    s = session("s1", "2026-11-03", [(80, 8)])
    s["entries"][0]["sets"][1]["at"] = "2026-11-03T07:05:00+00:00"
    client.post("/api/v1/gym/sessions", headers=AUTH, json=s)
    assert client.post("/api/v1/gym/effort/refresh", headers=AUTH).json() == {"waiting": 0}
    assert store.load().sessions[0].effort["bench-press"]["settle_s"] == 75
