"""9.6: what makes a good session: your workouts against sleep, resting heart rate, time of day and caffeine."""

from __future__ import annotations

from datetime import date, timedelta

from app.gym import good
from app.gym.store import GymDoc, Session

TODAY = date(2026, 11, 17)


def _doc(n: int = 20) -> tuple[GymDoc, list[dict]]:
    """Every other session after a good night is heavier: 100 kg against 92 kg for 5."""
    sessions, days = [], []
    for i in range(n):
        day = TODAY - timedelta(days=3 * (n - i))
        slept = i % 2 == 0
        w = 100 if slept else 92
        sessions.append(Session.model_validate({
            "id": f"s{i}", "title": "Legs", "started_at": f"{day}T{'07' if i % 3 else '19'}:00:00+00:00",
            "entries": [{"exercise": "back-squat", "sets": [{"weight": w, "reps": 5}, {"weight": w, "reps": 5}]}]}))
        days.append({"date": day.isoformat(), "metrics": {"sleep_hours": 7.6 if slept else 5.9, "resting_heart_rate": 55}})
    return GymDoc(sessions=sessions), days


def test_sleep_shows_up_and_nothing_else_does():
    doc, days = _doc()
    out = good.findings(doc, days, TODAY)
    assert out["scored"] >= 18
    keys = [f["key"] for f in out["findings"]]
    assert keys[0] == "sleep" and "resting_hr" not in keys and "caffeine" not in keys
    sleep = out["findings"][0]
    assert sleep["text"].startswith("You lift about ") and "more after 7 hours' sleep or more than after less" in sleep["text"]
    assert sleep["gap"] > 2


def test_too_little_to_go_on_says_so():
    doc, days = _doc(5)
    out = good.findings(doc, days, TODAY)
    assert out["findings"] == [] and out["note"].startswith("Not enough yet")
    assert good.findings(doc, None, TODAY)["health"] is False


def test_a_first_time_and_a_deload_dont_count():
    doc, days = _doc(6)
    doc.sessions[3].deload = True
    scored = good.scores(doc)
    assert "s0" not in scored and "s3" not in scored and "s1" in scored
