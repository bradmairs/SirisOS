"""9.6: assisted exercises (the weight is help: less is harder) and per-side exercises (volume counts both sides)."""

from __future__ import annotations

from app.gym import service, store
from app.gym.store import GymDoc, PlanExercise, Session
from tests.test_gym import AUTH, client, session  # noqa: F401 - the fixture


def _doc(*sessions: dict, **settings) -> GymDoc:
    doc = GymDoc(exercises=[
        store.CustomExercise(id="my-apu", name="Assisted Pull-Up", primary="back", equipment="machine"),
        store.CustomExercise(id="my-sar", name="Single Arm Dumbbell Row", primary="back", equipment="dumbbell"),
        store.CustomExercise(id="my-row", name="Barbell Row", primary="back", equipment="barbell"),
    ], sessions=[Session.model_validate(s) for s in sessions])
    doc.settings.bodyweight_kg = settings.get("bodyweight", 80)
    return doc


def test_flags_are_worked_out_from_the_name_and_can_be_changed():
    doc = _doc()
    ex = service.exercises(doc)
    assert ex["my-apu"]["assisted"] and not ex["my-apu"]["per_side"]
    assert ex["my-sar"]["per_side"] and not ex["my-sar"]["assisted"]
    assert not ex["my-row"]["assisted"] and not ex["my-row"]["per_side"]
    doc.loading["my-row"] = {"per_side": True}
    assert service.exercises(doc)["my-row"]["per_side"]


def test_less_help_is_a_record_and_the_1rm_is_what_you_lifted():
    doc = _doc(session("a", "2026-11-01", [(30, 8)], exercise="my-apu"), session("b", "2026-11-03", [(20, 8)], exercise="my-apu"))
    rows = service.history(doc, "my-apu")
    assert rows[-1]["e1rm"] == service.e1rm(60, 8)   # 80 kg less 20 kg of help
    rec = service.records(rows)
    assert rec["heaviest"]["weight"] == 20 and rec["heaviest"]["load"] == 60 and rec["heaviest"]["assisted"]
    found = service.new_records(doc, doc.sessions[-1])
    assert any(f["text"] == "Assisted Pull-Up: least help ever, 20 (you lifted 60)" for f in found)
    # More help is never a record.
    doc.sessions.append(Session.model_validate(session("c", "2026-11-05", [(40, 8)], exercise="my-apu")))
    assert not [f for f in service.new_records(doc, doc.sessions[-1]) if f["kind"] == "heaviest"]


def test_assisted_volume_and_what_to_lift_next():
    doc = _doc(session("a", "2026-11-03", [(25, 10), (25, 10), (25, 10)], exercise="my-apu"))
    e = doc.sessions[0].entries[0]
    assert service.entry_volume(doc, doc.sessions[0], e) == 3 * 55 * 10
    sug = service.suggest(doc, PlanExercise(exercise="my-apu", sets=3, reps="8-10"))
    assert sug["weight"] < 25 and "off the help" in sug["why"]
    doc.sessions[0].entries[0].sets[1].reps = 7
    sug = service.suggest(doc, PlanExercise(exercise="my-apu", sets=3, reps="8-10"))
    assert sug["weight"] == 25 and "Same help" in sug["why"]


def test_a_per_side_exercise_counts_both_sides():
    doc = _doc(session("a", "2026-11-03", [(30, 10), (30, 10)], exercise="my-sar"))
    assert service.entry_volume(doc, doc.sessions[0], doc.sessions[0].entries[0]) == 2 * 30 * 10 * 2
    assert service.history(doc, "my-sar")[-1]["e1rm"] == service.e1rm(30, 10)   # the 1RM stays per side


def test_set_loading_through_the_api(client):  # noqa: F811
    assert client.put("/api/v1/gym/exercises/bench-press/loading", headers=AUTH, json={"per_side": True}).json()["per_side"] is True
    got = client.get("/api/v1/gym/exercises/bench-press", headers=AUTH).json()["exercise"]
    assert got["per_side"] is True and got["assisted"] is False
    assert client.put("/api/v1/gym/exercises/nope/loading", headers=AUTH, json={"assisted": True}).status_code == 404


def test_a_saved_workout_says_which_exercises_are_assisted_or_per_side(client):  # noqa: F811
    client.post("/api/v1/gym/exercises", headers=AUTH, json={"name": "Assisted Dip", "primary": "triceps", "equipment": "machine"})
    ex = next(e for e in client.get("/api/v1/gym", headers=AUTH).json()["exercises"] if e["name"] == "Assisted Dip")
    assert ex["assisted"] is True
    assert client.post("/api/v1/gym/sessions", headers=AUTH, json=session("w1", "2026-11-03", [(25, 8)], exercise=ex["id"])).status_code == 200
    sid = "w1"
    got = client.get(f"/api/v1/gym/sessions/{sid}", headers=AUTH).json()["entries"][0]
    assert got["assisted"] is True and got["per_side"] is False


def test_a_percentage_chart_of_your_best_rounded_to_the_gym():
    """9.65: 50-95% of your best estimated 1RM, loadable at this gym, with about how many reps."""
    doc = _doc(session("a", "2026-11-03", [(100, 5)], exercise="my-row"))   # e1RM 116.7
    chart = service.percent_chart(doc, "my-row")
    rows = {r["percent"]: r for r in chart["rows"]}
    assert chart["best"] == 116.7 and [r["percent"] for r in chart["rows"]][:2] == [95, 90]
    assert rows[80]["weight"] == 92.5 and rows[80]["reps"] == 8   # 93.4 kg on a 20 kg bar with 1.25s: 92.5
    assert rows[95]["reps"] == 2 and rows[50]["reps"] is None
    assert all((r["weight"] - 20) % 2.5 == 0 for r in chart["rows"])
    # Assisted: the help that leaves you lifting that share (80 kg bodyweight).
    doc = _doc(session("b", "2026-11-03", [(20, 5)], exercise="my-apu"))   # 60 kg lifted, e1RM 70
    a = {r["percent"]: r for r in service.percent_chart(doc, "my-apu")["rows"]}
    assert a[90]["weight"] > 0 and a[90]["weight"] < a[50]["weight"]
    assert service.percent_chart(_doc(), "my-row") is None   # nothing logged yet
