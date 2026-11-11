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


# 6.6: bringing years of JEFIT (or any CSV) in.

JEFIT = """### WORKOUT SESSIONS ###
_id,mydate,starttime,total_time
1,2021-03-05,1614927600,3600

### EXERCISE LOGS ###
_id,mydate,eid,ename,logs
1,2021-03-05,1,Barbell Bench Press,"60x10,62.5x8,65x6"
2,2021-03-05,2,Cable Lat Pulldown,40x12
3,2021-03-08,3,Zercher Carry Thing,20x30
"""

PER_SET = """Date,Exercise,Set,Weight (lbs),Reps
05/03/2024,Back Squat,1,135,5
05/03/2024,Back Squat,2,185,5
"""


def _upload(client, body: bytes, name: str = "jefit.csv", **form):
    data = {k: (v if isinstance(v, str) else __import__("json").dumps(v)) for k, v in form.items()}
    return client.post("/api/v1/gym/import", headers=AUTH, files={"file": (name, body, "text/csv")}, data=data)


def test_importer_reads_both_shapes_pounds_and_dates():
    from app.gym import importer

    rows = importer.read_rows(JEFIT)
    assert [(r["exercise"], round(r["weight"], 1), r["reps"]) for r in rows][:3] == [("Barbell Bench Press", 60, 10), ("Barbell Bench Press", 62.5, 8), ("Barbell Bench Press", 65, 6)]
    assert len(rows) == 5  # the sessions table has no exercise column, so it's skipped
    squat = importer.read_rows(PER_SET)
    assert squat[0]["date"].isoformat() == "2024-03-05T00:00:00" and round(squat[1]["weight"], 2) == 83.91
    assert importer.parse_date("13/02/2023").month == 2 and importer.parse_date("1614927600").year == 2021
    assert importer.match("Barbell Bench Press", service.exercises(store.GymDoc()))[1] in ("exact", "close")


def test_import_previews_then_saves_once_however_often_its_sent(client):
    pre = _upload(client, JEFIT.encode()).json()["preview"]
    assert pre["sets"] == 5 and pre["workouts"] == 2 and pre["from"] == "2021-03-05" and pre["to"] == "2021-03-08"
    by = {e["name"]: e for e in pre["exercises"]}
    assert by["Barbell Bench Press"]["match"] == "bench-press" and by["Zercher Carry Thing"]["how"] == "none"
    assert client.get("/api/v1/gym", headers=AUTH).json()["total_sessions"] == 0  # a preview saves nothing

    choices = {"Cable Lat Pulldown": "new"}
    done = _upload(client, JEFIT.encode(), dry_run="false", choices=choices).json()["imported"]
    assert done == {"workouts": 2, "sets": 5, "new_exercises": 2, "skipped_days": [], "removed": 0, "tidied": 0}  # read as a JEFIT export (7.3)
    again = _upload(client, JEFIT.encode(), dry_run="false", choices=choices).json()["imported"]
    assert again["new_exercises"] == 0
    over = client.get("/api/v1/gym", headers=AUTH).json()
    assert over["total_sessions"] == 2 and _upload(client, JEFIT.encode()).json()["preview"]["replacing"] == 2
    bench = client.get("/api/v1/gym/exercises/bench-press", headers=AUTH).json()
    assert bench["records"]["heaviest"]["weight"] == 65 and bench["history"][0]["date"] == "2021-03-05"


def test_import_a_zip_in_pounds_saves_kilograms_and_says_what_it_needs(client):
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("export/logs.csv", PER_SET)
    assert _upload(client, buf.getvalue(), "jefit.zip", dry_run="false").json()["imported"]["sets"] == 2
    sid = client.get("/api/v1/gym/sessions", headers=AUTH).json()["sessions"][0]["id"]
    s = client.get(f"/api/v1/gym/sessions/{sid}", headers=AUTH).json()
    assert sid == "import-20240305" and [x["weight"] for x in s["entries"][0]["sets"]] == [61.23, 83.91]
    bad = _upload(client, b"name,colour\nx,blue\n")
    assert bad.status_code == 422 and "date and an exercise" in bad.json()["detail"]
    assert client.put("/api/v1/gym/settings", headers=AUTH, json={"unit": "lb"}).status_code == 422  # SI only


def test_a_gym_kept_in_pounds_is_converted_to_kilograms(client, tmp_path):
    import json

    (tmp_path / "gym.json").write_text(json.dumps({"settings": {"unit": "lb", "bar": 45, "plates": [45, 25], "increment": 5, "rest_s": 90},
        "sessions": [session("s1", "2026-11-02", [(225, 5)])]}))
    over = client.get("/api/v1/gym", headers=AUTH).json()
    assert {k: over["settings"][k] for k in ("unit", "bar", "plates", "increment", "rest_s")} == {"unit": "kg", "bar": 20.41, "plates": [20.41, 11.34], "increment": 2.27, "rest_s": 90}
    assert client.get("/api/v1/gym/exercises/bench-press", headers=AUTH).json()["records"]["heaviest"]["weight"] == 102.06


# 6.7: gyms, warm-ups, progression rules, effort, supersets, heatmap.

def _routine(client, **plan) -> str:
    body = {"routine": {"name": "Test", "days": [{"name": "A", "exercises": [{"exercise": "bench-press", "sets": 3, "reps": "5-8", **plan}]}], "active": True}}
    return client.post("/api/v1/gym/routines", headers=AUTH, json=body).json()["id"]


def test_gym_profiles_round_to_what_the_gym_has_and_warm_ups_load_the_bar(client):
    s = client.get("/api/v1/gym", headers=AUTH).json()["settings"]
    assert s["current_gym"] == "home" and s["gyms"][0]["bar"] == 20
    s["gyms"].append({"id": "work", "name": "Work gym", "bar": 15, "plates": [20, 10, 5, 2.5], "dumbbells": [10, 12.5, 15, 17.5, 20], "stack_step": 5})
    s["current_gym"] = "work"
    saved = client.put("/api/v1/gym/settings", headers=AUTH, json=s).json()
    assert saved["bar"] == 15 and saved["plates"] == [20, 10, 5, 2.5]  # the current gym's
    doc = store.load()
    assert service.loadable(doc, "bench-press", 83) == 85 and service.loadable(doc, "db-curl", 14) == 15  # 5 kg steps; nearest dumbbell
    assert service.loadable(doc, "lat-pulldown", 47) == 45
    warm = client.get("/api/v1/gym/warmups?exercise=bench-press&weight=100&gym=home", headers=AUTH).json()["warmups"]
    assert warm == [{"weight": 20, "reps": 10}, {"weight": 40, "reps": 5}, {"weight": 60, "reps": 3}, {"weight": 80, "reps": 2}]
    rid = _routine(client)
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("s1", "2026-11-02", [(100, 8), (100, 8), (100, 8)]))
    p = client.get(f"/api/v1/gym/plan?routine={rid}&gym=home", headers=AUTH).json()["exercises"][0]
    assert p["suggest"]["weight"] == 102.5 and p["warmups"][-1] == {"weight": 82.5, "reps": 2}
    assert client.get("/api/v1/gym/sessions/s1", headers=AUTH).json()["gym"] == "work"


def test_easy_sets_add_more_a_grind_holds_and_last_notes_come_back(client):
    rid = _routine(client)
    easy = session("s1", "2026-11-02", [(80, 8), (80, 8)])
    easy["entries"][0]["sets"] = [{**x, "rpe": 7} for x in easy["entries"][0]["sets"]]
    easy["entries"][0]["note"] = "Left shoulder niggle"
    client.post("/api/v1/gym/sessions", headers=AUTH, json=easy)
    p = client.get(f"/api/v1/gym/plan?routine={rid}", headers=AUTH).json()["exercises"][0]["suggest"]
    assert p["weight"] == 85 and "felt easy" in p["why"] and p["last_note"] == "Left shoulder niggle"
    grind = session("s2", "2026-11-04", [(85, 6), (85, 5)])
    grind["entries"][0]["sets"][-1]["rpe"] = 10
    client.post("/api/v1/gym/sessions", headers=AUTH, json=grind)
    p = client.get(f"/api/v1/gym/plan?routine={rid}", headers=AUTH).json()["exercises"][0]["suggest"]
    assert p["weight"] == 85 and "grind" in p["why"]


def test_linear_backs_off_after_two_misses_and_percent_uses_the_training_max(client):
    rid = _routine(client, reps="5", progression="linear")
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("s1", "2026-10-28", [(100, 4), (100, 5)]))
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("s2", "2026-11-02", [(100, 4), (100, 3)]))
    p = client.get(f"/api/v1/gym/plan?routine={rid}", headers=AUTH).json()["exercises"][0]["suggest"]
    assert p["weight"] == 90 and "back off" in p["why"]
    rid2 = _routine(client, reps="5", progression="percent", percents=[0.7, 0.8, 0.9])
    p = client.get(f"/api/v1/gym/plan?routine={rid2}", headers=AUTH).json()["exercises"][0]["suggest"]
    # best e1RM 100×5 = 116.7; training max 105; 70/80/90% loadable in 2.5 kg steps
    assert p["training_max"] == 105 and p["per_set"] == [72.5, 85, 95]


def test_supersets_keep_their_group_and_the_heatmap_counts_each_day(client):
    s = session("s1", "2026-11-02", [(80, 8)])
    s["entries"][0]["group"] = "A"
    s["entries"].append({"exercise": "barbell-row", "group": "A", "sets": [{"weight": 60, "reps": 10}]})
    client.post("/api/v1/gym/sessions", headers=AUTH, json=s)
    assert [e["group"] for e in client.get("/api/v1/gym/sessions/s1", headers=AUTH).json()["entries"]] == ["A", "A"]
    days = client.get("/api/v1/gym/heatmap", headers=AUTH).json()["days"]
    assert days == [{"date": "2026-11-02", "volume": 80 * 8 + 600, "sets": 2, "muscles": ["chest", "back"]}]


# 6.8: muscle targets, deloads, readiness, strength, the year, the Watch, strain.

@pytest.fixture
def health(monkeypatch):
    from app.gym import api as gym_api

    state = {"readiness": None, "recent": [], "weight_kg": None, "weight_series": [], "sent": [], "workouts": []}

    async def fake_health(hub):
        return {k: state[k] for k in ("readiness", "recent", "weight_kg", "weight_series")}

    async def fake_send(hub, doc, day):
        from app.gym import coach
        state["sent"].append(coach.as_workouts(doc, day))

    async def fake_workouts(hub, days=42):
        return state["workouts"]

    from app.health import service as health_service
    monkeypatch.setattr(gym_api, "_health", fake_health)
    monkeypatch.setattr(gym_api, "_send_day", fake_send)
    monkeypatch.setattr(health_service, "workouts", fake_workouts)
    return state


def test_sets_per_muscle_against_targets_and_a_deload_when_lifts_stall(client, health):
    for i, d in enumerate(["2026-10-12", "2026-10-19", "2026-10-26", "2026-11-02"]):
        client.post("/api/v1/gym/sessions", headers=AUTH, json=session(f"s{i}", d, [(100, 5)] * (12 if i == 3 else 1)))
    over = client.get("/api/v1/gym", headers=AUTH).json()
    chest = next(m for m in over["muscles"] if m["muscle"] == "chest")
    assert chest == {"muscle": "chest", "sets": 12, "target": [10, 20], "status": "in range"}
    assert next(m for m in over["muscles"] if m["muscle"] == "back")["status"] == "under"
    assert over["deload"]["suggest"] and "Bench Press has stalled" in over["deload"]["why"][0]
    on = client.post("/api/v1/gym/deload", headers=AUTH, json={"on": True}).json()
    assert on["active"] and on["until"] == "2026-11-10"
    rid = _routine(client)
    p = client.get(f"/api/v1/gym/plan?routine={rid}", headers=AUTH).json()
    assert p["deload"] and p["exercises"][0]["sets"] == 2 and p["exercises"][0]["suggest"]["weight"] == 90
    dl = session("d1", "2026-11-04", [(150, 5)])
    dl["deload"] = True
    assert client.post("/api/v1/gym/sessions", headers=AUTH, json=dl).json()["records"] == []  # no records in a deload


def test_readiness_shapes_the_plan_and_low_mornings_suggest_a_deload(client, health):
    rid = _routine(client)
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("s1", "2026-11-02", [(100, 6), (100, 6), (100, 6)]))
    health["readiness"] = {"score": 38, "band": "Recover"}
    p = client.get(f"/api/v1/gym/plan?routine={rid}", headers=AUTH).json()
    assert p["readiness"] == {"score": 38, "band": "Recover"}
    assert p["exercises"][0]["sets"] == 2 and p["exercises"][0]["suggest"]["weight"] == 95 and "Readiness is low today (38)" in p["exercises"][0]["suggest"]["why"]
    health["readiness"] = {"score": 88, "band": "Primed"}
    assert client.get(f"/api/v1/gym/plan?routine={rid}", headers=AUTH).json()["exercises"][0]["suggest"]["push"] is True
    health["recent"] = [{"band": "Recover"}, {"band": "Steady"}, {"band": "Recover"}, {"band": "Recover"}]
    assert "readiness has been low on 3" in client.get("/api/v1/gym", headers=AUTH).json()["deload"]["why"][-1]


def test_strength_against_bodyweight_and_the_year_in_review(client, health):
    health["weight_kg"] = 80
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("a", "2025-06-01", [(90, 5)]))
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("b", "2026-03-01", [(100, 5)]))
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("c", "2026-03-15", [(105, 3)]))
    st = client.get("/api/v1/gym/strength", headers=AUTH).json()
    bench = st["lifts"][0]
    assert st["bodyweight"] == 80 and bench["best"] == 116.7 and bench["ratio"] == 1.46 and bench["level"] == "intermediate"
    assert bench["this_year"] == 116.7 and bench["last_year"] == 105
    y = client.get("/api/v1/gym/year?year=2026", headers=AUTH).json()
    assert y["sessions"] == 2 and y["previous"]["sessions"] == 1 and y["months"][2]["sessions"] == 2
    assert y["months"][2]["records"] >= 1 and y["best"][0]["e1rm"] == 116.7 and y["muscles"][0]["muscle"] == "chest"


def test_a_session_goes_to_sirisai_and_shows_the_watch_workout(client, health):
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("s1", "2026-11-02", [(80, 8)]))
    sent = health["sent"][-1]
    assert list(sent["workouts"]) == ["2026-11-02"] and sent["workouts"]["2026-11-02"][0]["minutes"] == 65
    assert sent["workouts"]["2026-11-02"][0]["name"] == "SirisGym: Push"
    # 07:00 UTC is 18:00 in Melbourne; the Watch workout started at 18:03 local.
    health["workouts"] = [{"date": "2026-11-02", "name": "Traditional Strength Training", "start": "2026-11-02 18:03:00 +1100", "minutes": 61,
                           "kcal": 420, "avg_hr": 118, "max_hr": 161, "source": "health_auto_export"},
                          {"date": "2026-11-02", "name": "SirisGym: Push", "start": "2026-11-02 18:00:00 +1100", "minutes": 65, "source": "sirisgym"}]
    w = client.get("/api/v1/gym/sessions/s1", headers=AUTH).json()["watch"]
    assert w == {"name": "Traditional Strength Training", "start": "2026-11-02 18:03:00 +1100", "minutes": 61, "avg_hr": 118, "max_hr": 161, "kj": 1757}


# 6.9: the programme builder, measurements, photos, the rest push, the summary for SirisAI.

def test_the_builder_reads_a_goal_and_spares_an_injury(client):
    r = client.post("/api/v1/gym/builder", headers=AUTH, json={"text": "4 days, hypertrophy, bad left shoulder, 60 minutes"}).json()
    assert r["chosen"] == {"days": 4, "goal": "muscle", "minutes": 60, "equipment": "gym", "avoid": ["shoulder"]}
    ids = {e["exercise"] for d in r["routine"]["days"] for e in d["exercises"]}
    assert [d["name"] for d in r["routine"]["days"]] == ["Upper 1", "Lower 1", "Upper 2", "Lower 2"]
    assert not ids & {"overhead-press", "bench-press", "dip", "db-shoulder-press"} and "db-bench-press" in ids
    home = client.post("/api/v1/gym/builder", headers=AUTH, json={"text": "3 days at home with dumbbells, strength, sore knee"}).json()
    from app.gym import library
    used = [library.BUILTIN[e["exercise"]] for d in home["routine"]["days"] for e in d["exercises"]]
    assert {u["equipment"] for u in used} <= {"dumbbell", "bodyweight", "kettlebell", "band", "other"}
    assert not {e["exercise"] for d in home["routine"]["days"] for e in d["exercises"]} & {"bulgarian-split-squat", "goblet-squat", "walking-lunge"}
    # It's a draft: saving it goes through the routine editor.
    assert client.get("/api/v1/gym", headers=AUTH).json()["routines"] == []


def test_measurements_and_photos_are_kept_privately(client, health, tmp_path):
    health["weight_series"] = [{"date": "2026-11-01", "weight": 81.2, "trend": 81.5}]
    client.post("/api/v1/gym/measurements", headers=AUTH, json={"id": "m1", "date": "2026-11-01", "waist": 84.5, "arm": 38})
    up = client.post("/api/v1/gym/photos", headers=AUTH, files={"file": ("front.jpg", b"\xff\xd8\xff fake jpeg", "image/jpeg")},
                     data={"date": "2026-11-01", "pose": "front"}).json()
    body = client.get("/api/v1/gym/body", headers=AUTH).json()
    assert body["measurements"][0]["waist"] == 84.5 and body["photos"][0]["pose"] == "front" and "file" not in body["photos"][0]
    assert body["weight"] == [{"date": "2026-11-01", "kg": 81.2, "trend": 81.5}]
    got = client.get(f"/api/v1/gym/photos/{up['id']}", headers=AUTH)
    assert got.status_code == 200 and got.content.startswith(b"\xff\xd8")
    assert client.get(f"/api/v1/gym/photos/{up['id']}").status_code == 401
    assert client.post("/api/v1/gym/photos", headers=AUTH, files={"file": ("x.txt", b"hi", "text/plain")}, data={"date": "2026-11-01"}).status_code == 415
    client.delete(f"/api/v1/gym/photos/{up['id']}", headers=AUTH)
    assert not list((tmp_path / "gym-photos").iterdir())


def test_the_rest_timer_rings_on_the_lock_screen(client, monkeypatch):
    import asyncio
    from app.gym import api as gym_api
    from app.push import notifier

    sent = []

    async def deliver(messages):
        sent.extend(messages)
        return len(messages)

    monkeypatch.setattr(notifier, "deliver", deliver)
    monkeypatch.setattr(gym_api.asyncio, "sleep", lambda s: asyncio.sleep(0))
    client.post("/api/v1/gym/rest", headers=AUTH, json={"seconds": 90, "next": "Bench Press, set 3"})
    client.post("/api/v1/gym/rest", headers=AUTH, json={"seconds": 60, "next": "Barbell Row, set 1"})
    client.delete("/api/v1/gym/rest", headers=AUTH)
    assert all(m["topic"] == "gym" and m["url"] == "/gym/workout" for m in sent)


def test_the_summary_for_sirisai_has_the_lifts_and_whats_next(client, health):
    from app.gym import coach

    rid = _routine(client)
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("s1", "2026-10-28", [(80, 8), (80, 8), (80, 8)], routine=rid, d=0))
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("s2", "2026-11-03", [(85, 8), (85, 8), (85, 8)], routine=rid, d=0))
    s = coach.for_sirisai(store.load(), TODAY)
    assert s["lifts"]["Bench Press"]["best"] == 107.7 and len(s["lifts"]["Bench Press"]["last"]) == 2
    assert s["next"]["exercises"][0] == {"name": "Bench Press", "sets": 3, "reps": "5-8", "weight": 87.5, "why": "Last time every set at 85 reached 8: add 2.5."}
    assert any("Bench Press" in r for r in s["records_30d"]) and s["streak_weeks"] == 2


# 6.93: swap, protein, a gym slot, the brief, test sync, the inspector.

def test_swap_offers_the_same_movement_first(client):
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("s1", "2026-11-02", [(30, 10)], exercise="db-bench-press"))
    opts = client.get("/api/v1/gym/swap?exercise=bench-press", headers=AUTH).json()["options"]
    assert opts[0]["id"] == "db-bench-press" and opts[0]["same_pattern"] and opts[0]["last"][0]["weight"] == 30
    assert all(o["id"] != "bench-press" for o in opts) and any(not o["same_pattern"] for o in opts)


def test_protein_target_from_bodyweight_and_training(client, health, monkeypatch):
    from app.hub import sirisai_api

    async def get(hub, path, params=None, timeout=20.0):
        return {"days": [{"date": TODAY.isoformat(), "metrics": {"protein_g": 95, "meal_protein_g_estimate": 120}}]}

    monkeypatch.setattr(sirisai_api, "get", get)
    health["weight_kg"] = 80
    p = client.get("/api/v1/gym/protein", headers=AUTH).json()
    assert p == {"target_g": 128, "eaten_g": 120, "per_kg": 1.6, "bodyweight": 80, "training_day": False, "has_routine": False, "left_g": 8}
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("t", TODAY.isoformat(), [(80, 5)]))
    assert client.get("/api/v1/gym/protein", headers=AUTH).json()["target_g"] == 160


def test_a_free_slot_for_the_gym_and_adding_it(client, monkeypatch):
    from datetime import datetime as dt

    from app.calendar import service as calendar
    from app.gym import coach
    from app.health import service as health_service
    from app.tasks.service import zone

    tz = zone()
    day = TODAY
    busy = [{"start": dt(day.year, day.month, day.day, 6, 0, tzinfo=tz).isoformat(), "end": dt(day.year, day.month, day.day, 9, 0, tzinfo=tz).isoformat()},
            {"start": dt(day.year, day.month, day.day, 12, 0, tzinfo=tz).isoformat(), "end": dt(day.year, day.month, day.day, 13, 30, tzinfo=tz).isoformat()}]
    early = dt(day.year, day.month, day.day, 5, 0, tzinfo=tz)
    a, b = coach.free_slot(busy, day, 60, now=early)
    assert (a.hour, a.minute, b.hour, b.minute) == (17, 0, 18, 0)  # 6-8 taken, lunch only has 30 min, so after work

    async def events(hub, start, end):
        return {"events": busy}

    added = []

    async def tool(hub, name, arguments=None):
        added.append((name, arguments))
        return {"created": True}

    monkeypatch.setattr(calendar, "events", events)
    monkeypatch.setattr(health_service, "tool", tool)
    monkeypatch.setattr(coach, "free_slot", lambda ev, d, m, now=None: (dt(d.year, d.month, d.day, 17, tzinfo=tz), dt(d.year, d.month, d.day, 18, tzinfo=tz)))
    rid = _routine(client)
    preview = client.post("/api/v1/gym/schedule", headers=AUTH, json={"minutes": 60}).json()
    assert preview["title"] == "Gym: A" and preview["slot"]["start"].endswith("17:00+11:00") and not added
    done = client.post("/api/v1/gym/schedule", headers=AUTH, json={"minutes": 60, "dry_run": False}).json()
    assert done["added"] and added[0][0] == "calendar_create_event" and added[0][1]["summary"] == "Gym: A"
    assert rid


def test_the_brief_has_todays_gym_day(client):
    from app.brief.service import _gym_today

    assert _gym_today(TODAY, None) is None
    rid = _routine(client)
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("s1", "2026-11-02", [(80, 8), (80, 8), (80, 8)], routine=rid, d=0))
    g = _gym_today(TODAY, {"band": "Recover", "score": 40})
    assert g["title"] == "Test: A" and g["lifts"][0] == {"name": "Bench Press", "sets": 2, "reps": "5-8", "weight": 77.5}  # 82.5 next, 5% off, to 2.5 kg and "low" in g["note"]
    assert g["days_since"] == 2


def test_test_sync_and_the_inspector(client, monkeypatch):
    from app.hub import sirisai_api
    from app.tasks.service import today

    async def post(hub, path, json=None, headers=None, timeout=20.0, **kw):
        assert path.endswith("dry_run=1")
        day = json["data"]["metrics"][0]["data"][0]["date"][:10]
        return {"dry_run": True, "meta": {"last_day": day}, "days": {day: {"steps": 1.0}}}

    async def get(hub, path, params=None, timeout=20.0):
        return {"day": params["day"], "metrics": [{"metric": "steps", "trusted": "health_auto_export", "value": 50, "sources": []}]}

    monkeypatch.setattr(sirisai_api, "post", post)
    monkeypatch.setattr(sirisai_api, "get", get)
    r = client.post("/api/v1/health/import/test", headers=AUTH).json()
    assert r["ok"] and "read an export for this hour correctly" in r["detail"]
    assert client.get("/api/v1/health/sources?day=2026-11-01", headers=AUTH).json()["metrics"][0]["trusted"] == "health_auto_export"


# 6.94: routine days on set weekdays.

def test_days_on_set_weekdays_pick_todays_and_rest_days_say_whats_next(client):
    body = {"routine": {"name": "PPL", "active": True, "days": [
        {"name": "Push", "weekdays": [0, 3], "exercises": [{"exercise": "bench-press", "sets": 3, "reps": "5-8"}]},
        {"name": "Pull", "weekdays": [1, 4], "exercises": [{"exercise": "barbell-row", "sets": 3, "reps": "8-10"}]},
        {"name": "Legs", "weekdays": [2, 9, 2], "exercises": [{"exercise": "back-squat", "sets": 3, "reps": "5-8"}]}]}}
    rid = client.post("/api/v1/gym/routines", headers=AUTH, json=body).json()["id"]
    assert [d["weekdays"] for d in client.get("/api/v1/gym", headers=AUTH).json()["routines"][0]["days"]] == [[0, 3], [1, 4], [2]]
    # TODAY is a Wednesday: Legs, even though nothing's been done yet.
    over = client.get("/api/v1/gym", headers=AUTH).json()["active"]
    assert over["next_day"] == 2 and over["schedule"]["today"] == 2 and not over["schedule"]["rest"]
    assert [w["name"] for w in over["schedule"]["week"]] == ["Push", "Pull", "Legs", "Push", "Pull", None, None]
    assert client.get(f"/api/v1/gym/plan?routine={rid}", headers=AUTH).json()["title"] == "PPL: Legs"
    from datetime import date
    sched = service.schedule(store.load(), rid, date(2026, 11, 7))  # a Saturday
    assert sched["rest"] and sched["next"] == {"day": 0, "date": "2026-11-09", "weekday": "Monday"}
    assert service.next_day(store.load(), rid, date(2026, 11, 7)) == 0
    from app.gym import coach
    assert coach.today_for_brief(store.load(), date(2026, 11, 7), None) == {"done": False, "rest": True, "title": "PPL: rest day, Push on Monday"}


def test_routines_without_weekdays_still_go_in_turn_and_the_builder_spreads_the_week(client):
    rid = _routine(client)
    over = client.get("/api/v1/gym", headers=AUTH).json()["active"]
    assert over["schedule"] is None and over["next_day"] == 0
    r = client.post("/api/v1/gym/builder", headers=AUTH, json={"text": "3 days"}).json()
    assert [d["weekdays"] for d in r["routine"]["days"]] == [[0], [2], [4]]
    assert rid


# 6.95: no duplicate workouts from JEFIT, and no exercises made from workout names.

def test_a_sessions_table_isnt_exercises_and_repeated_sets_count_once(client):
    from app.gym import importer

    text = """### WORKOUT SESSIONS ###
_id,mydate,name,total_time
1,2021-03-05,Push Day,3600

### EXERCISE LOGS ###
_id,mydate,eid,ename,logs
1,2021-03-05,1,Barbell Bench Press,"60x10,62.5x8"
1,2021-03-05,1,Barbell Bench Press,"60x10,62.5x8"
2,2021-03-05,2,Lat Pulldown,
"""
    rows = importer.read_rows(text)
    assert [(r["exercise"], r["weight"], r["reps"]) for r in rows] == [("Barbell Bench Press", 60.0, 10), ("Barbell Bench Press", 62.5, 8)]


def test_days_already_logged_in_sirisgym_arent_imported_again(client):
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("live", "2021-03-05", [(60, 10)]))
    pre = _upload(client, JEFIT.encode()).json()["preview"]
    assert pre["already_logged"] == ["2021-03-05"]
    done = _upload(client, JEFIT.encode(), dry_run="false").json()["imported"]
    assert done["skipped_days"] == ["2021-03-05"] and done["workouts"] == 1
    days = [s["date"] for s in client.get("/api/v1/gym/sessions", headers=AUTH).json()["sessions"]]
    assert sorted(days) == ["2021-03-05", "2021-03-08"]  # one workout on the 5th, not two


def test_the_one_time_tidy_removes_exercises_with_no_data_and_keeps_workouts(client, tmp_path):
    import json

    raw = {"exercises": [{"id": "my-push", "name": "Push Day", "primary": "full body"}, {"id": "my-zercher", "name": "Zercher", "primary": "quads"},
                         {"id": "my-plan", "name": "Planned", "primary": "back"}],
           "routines": [{"id": "r", "name": "R", "days": [{"name": "A", "exercises": [{"exercise": "my-plan"}]}]}],
           "sessions": [{"id": "import-20210305", "title": "Imported workout", "started_at": "2021-03-05T07:00:00", "entries": [
               {"exercise": "my-push", "sets": [{"done": True}, {"done": True}]},
               {"exercise": "bench-press", "sets": [{"weight": 60, "reps": 10}, {"done": True}]},
               {"exercise": "my-zercher", "sets": [{"weight": 40, "reps": 8}]}]}]}
    (tmp_path / "gym.json").write_text(json.dumps(raw))
    over = client.get("/api/v1/gym", headers=AUTH).json()
    names = {e["name"] for e in over["exercises"] if e["custom"]}
    assert names == {"Zercher", "Planned"} and over["total_sessions"] == 1
    s = client.get("/api/v1/gym/sessions/import-20210305", headers=AUTH).json()
    assert [e["exercise"] for e in s["entries"]] == ["bench-press", "my-zercher"] and len(s["entries"][0]["sets"]) == 1
    assert list(tmp_path.glob("gym.before-cleanup.*.json"))
    # Once only: a new exercise of yours with nothing logged yet stays.
    client.post("/api/v1/gym/exercises", headers=AUTH, json={"name": "Landmine Press", "primary": "shoulders"})
    assert any(e["name"] == "Landmine Press" for e in client.get("/api/v1/gym", headers=AUTH).json()["exercises"])
    assert client.post("/api/v1/gym/cleanup?dry_run=true", headers=AUTH).json()["names"] == ["Landmine Press"]
# 6.96: set times go to SirisAI, and the effort comes back.

def test_set_times_go_to_sirisai_and_the_effort_comes_back(client, monkeypatch):
    from app.hub import sirisai_api

    posted, asked = [], []

    async def post(hub, path, json=None, headers=None, timeout=20.0, **kw):
        posted.append((path, json))
        return {"kept": True}

    async def get(hub, path, params=None, timeout=20.0):
        asked.append(path)
        return {"linked": True, "text": "Hardest: Bench Press", "exercises": [{"exercise": "Bench Press", "effort": 7.5}]}

    monkeypatch.setattr(sirisai_api, "post", post)
    monkeypatch.setattr(sirisai_api, "get", get)
    s = session("s1", "2026-11-02", [(80, 8)])
    s["entries"][0]["sets"][1].update(at="2026-11-02T07:04:40+00:00", rpe=8)
    client.post("/api/v1/gym/sessions", headers=AUTH, json=s)
    sent = next(j for p, j in posted if p == "/siris/health/gym/session")
    assert sent["id"] == "s1" and sent["sets"][1] == {"exercise": "bench-press", "name": "Bench Press", "set": 1, "type": "normal", "weight": 80.0, "reps": 8,
                                                     "seconds": None, "rpe": 8.0, "at": "2026-11-02T07:04:40+00:00", "group": None}
    assert sent["sets"][0]["type"] == "warmup" and sent["sets"][0]["set"] == 0
    e = client.get("/api/v1/gym/sessions/s1/effort", headers=AUTH).json()
    assert e["linked"] and asked == ["/siris/health/gym/session/s1/analysis"]
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("s2", "2026-11-03", [(80, 8)]))
    assert not client.get("/api/v1/gym/sessions/s2/effort", headers=AUTH).json()["linked"]  # no set times


def test_jefit_timestamps_are_local_and_old_imports_move_to_their_local_day(client, tmp_path):
    import json

    from app.gym import importer

    # 1730848423 is 2024-11-05 23:13:43 UTC, 10:13am on the 6th in Melbourne.
    rows = importer.read_rows("timestamp,exercise,weight,reps,set\n1730848423,Bench Press,80,8,1\n")
    assert rows[0]["date"].isoformat() == "2024-11-06T10:13:43"
    raw = {"cleaned_empty": True, "sessions": [
        {"id": "import-20241105", "title": "Imported workout", "started_at": "2024-11-05T23:13:43", "entries": [{"exercise": "bench-press", "sets": [{"weight": 80, "reps": 8}]}]},
        {"id": "import-20241106", "title": "Imported workout", "started_at": "2024-11-06T21:00:00", "entries": [{"exercise": "back-squat", "sets": [{"weight": 100, "reps": 5}]}]},
        {"id": "import-20210305", "title": "Imported workout", "started_at": "2021-03-05T07:00:00", "entries": [{"exercise": "deadlift", "sets": [{"weight": 140, "reps": 3}]}]}]}
    (tmp_path / "gym.json").write_text(json.dumps(raw))
    ids = sorted(s["id"] for s in client.get("/api/v1/gym/sessions", headers=AUTH).json()["sessions"])
    assert ids == ["import-20210305", "import-20241106", "import-20241107"]  # 07:00 (no time) left alone
    s = client.get("/api/v1/gym/sessions/import-20241106", headers=AUTH).json()
    assert s["started_at"] == "2024-11-06T10:13:43" and [e["exercise"] for e in s["entries"]] == ["bench-press"]
    assert list(tmp_path.glob("gym.before-local-times.*.json"))


JEFIT_EXPORT = """
### SETTING ##########################################

row_id,USERID,TIMESTAMP,gender,mass
1,8423258,"2026-10-12 20:31:59",M," kg"
######################################################

### ROUTINES #########################################

row_id,USERID,TIMESTAMP,belongSys,superset,_id,exercisename,logs
9,8423258,"2026-11-05 21:00:00",1,0,5,"EZ Bar Skull Crusher","27.5x10,37.5x8,37.5x10"
######################################################

### WORKOUT SESSIONS #################################

rowid,_id,USERID,edit_time,day_id,total_time,starttime,endtime,TIMESTAMP
1,1793822104,8423258,0,0,2205,1793822104,1793824309,"2026-11-05 20:37:17"
2,1793908155,8423258,0,0,2876,1793908155,1793911031,"2026-11-05 20:37:14"
######################################################

### EXERCISE LOGS ####################################

USERID,TIMESTAMP,belongSys,logs,_id,record,mydate,eid,ename,day_item_id,belongsession,logTime
8423258,"2026-11-04 20:04:50",1,"20.0x10,30.0x10,30.0x12",100391,42,2026-11-05,112,"Barbell Curl",1,1793822104,1793822687
8423258,"2026-11-04 20:31:42",1,"53.0x10,60.0x10,67.0x10",100394,89,2026-11-05,253,"Machine Tricep Extension",2,1793822104,1793824300
8423258,"2026-11-05 20:23:18",1,"12.5x8,12.5x10,12.5x12",100397,17.5,2026-11-06,32,"Dumbbell Lateral Raise",3,1793908155,1793910197
8423258,"2026-11-05 20:23:18",1,"12.5x8,12.5x10,12.5x12",100397,17.5,2026-11-06,32,"Dumbbell Lateral Raise",3,1793908155,1793910197
######################################################

### EXERCISE SET LOGS ################################

_id,userid,exercise_log_id,set_index,weight_lbs,reps,log_time,TIMESTAMP
1,8423258,100397,0,27.5577,8,1793909589,"2026-11-05 20:23:18"
2,8423258,100397,1,27.5577,10,1793909793,"2026-11-05 20:23:18"
3,8423258,100397,2,27.5577,12,1793910198,"2026-11-05 20:23:18"
######################################################

### EXERCISE RECORDS #################################

USERID,TIMESTAMP,eid,ename,record,mydate
8423258,"2026-11-05 20:00:00",1,"Front Raise","12.5x10",2026-11-05
######################################################
"""


def test_a_jefit_export_imports_only_logged_exercises_on_their_melbourne_day(client, tmp_path):
    """7.3: Friday 7am in Melbourne is Thursday evening UTC; routines and records aren't workouts; a log repeated is kept once;
    "Machine Tricep Extension" isn't the dumbbell overhead extension; an older wrong import of those days is taken out."""
    import json

    old = {"cleaned_empty": True, "import_times_local": True, "import_titles": True, "sessions": [
        {"id": "import-20261104", "title": "Wrong", "started_at": "2026-11-05T07:04:00", "entries": [{"exercise": "barbell-curl", "sets": [{"weight": 20, "reps": 10}]}]}]}
    (tmp_path / "gym.json").write_text(json.dumps(old))
    files = {"file": ("Bmairs_20261105.csv", JEFIT_EXPORT.encode(), "text/csv")}
    pre = client.post("/api/v1/gym/import", headers=AUTH, files=files, data={"dry_run": "true"}).json()["preview"]
    assert pre["jefit"] and pre["workouts"] == 2 and pre["sets"] == 9 and pre["removing"] == 1
    m = {e["name"]: e for e in pre["exercises"]}
    assert set(m) == {"Barbell Curl", "Machine Tricep Extension", "Dumbbell Lateral Raise"}  # no routine or record exercises
    assert m["Machine Tricep Extension"]["match"] is None and m["Dumbbell Lateral Raise"]["match"] == "lateral-raise"
    r = client.post("/api/v1/gym/import", headers=AUTH, files=files, data={"dry_run": "false"}).json()["imported"]
    assert r["workouts"] == 2 and r["removed"] == 1
    got = {s["id"]: s for s in client.get("/api/v1/gym/sessions", headers=AUTH).json()["sessions"]}
    assert set(got) == {"import-20261105", "import-20261106"}
    fri = client.get("/api/v1/gym/sessions/import-20261106", headers=AUTH).json()
    assert fri["started_at"] == "2026-11-06T06:49:15" and fri["ended_at"] == "2026-11-06T07:37:11"
    assert [(x["weight"], x["reps"]) for x in fri["entries"][0]["sets"]] == [(12.5, 8), (12.5, 10), (12.5, 12)]
    assert fri["entries"][0]["sets"][0]["at"] == "2026-11-05T20:13:09+00:00"
    thu = client.get("/api/v1/gym/sessions/import-20261105", headers=AUTH).json()
    assert [e["name"] for e in thu["entries"]] == ["Barbell Curl", "Machine Tricep Extension"]
    assert list(tmp_path.glob("gym.before-jefit.*.json"))


def test_sirisai_reads_sessions_with_the_service_key_but_never_writes(client, monkeypatch):
    key = "g" * 32
    service_auth = {"Authorization": f"Bearer {key}"}
    monkeypatch.setenv("SIRISOS_SERVICE_KEY", key)
    client.post("/api/v1/gym/sessions", headers=AUTH, json=session("s9", "2026-11-02", [(80, 8)]))
    listed = client.get("/api/v1/gym/sessions?month=2026-11", headers=service_auth)
    assert listed.status_code == 200 and listed.json()["sessions"][0]["id"] == "s9"
    one = client.get("/api/v1/gym/sessions/s9?watch=false", headers=service_auth).json()
    assert one["watch"] is None and one["entries"][0]["sets"][1]["weight"] == 80
    assert client.post("/api/v1/gym/sessions", headers=service_auth, json=session("s10", "2026-11-03", [(80, 8)])).status_code == 403
    assert client.delete("/api/v1/gym/sessions/s9", headers=service_auth).status_code == 403
