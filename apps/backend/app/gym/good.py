"""What makes a good session (9.6): your best and worst workouts against sleep,
resting heart rate, time of day and caffeine, from your own history.

- **How good a session was**: for each exercise with an estimated 1RM, that
  against your best for it in the 90 days before; the session's score is the
  average, as a percentage (100 = matched your recent best). A first time at an
  exercise, a deload or a held import doesn't count.
- **The things it's compared with**, from Apple Health through SirisAI, for the
  session's own day: sleep the night before (7 hours or more against less),
  resting heart rate (at or below your usual, the median, against above),
  time of day (before noon against after) and caffeine that day (100 mg or
  more against less, only on days anything was logged).
- A finding needs at least four sessions on each side and a difference of
  2 points or more, so a couple of odd days don't make a rule.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from statistics import median
from typing import Any

from app.gym import coach, service
from app.gym.store import GymDoc, counted

WINDOW_DAYS = 90
MIN_EACH_SIDE = 4
MIN_GAP = 2.0  # percentage points


def scores(doc: GymDoc, since: date | None = None) -> dict[str, dict[str, Any]]:
    """{session id: {date, hour, score}} for the sessions that can be scored."""
    by_session: dict[str, list[float]] = defaultdict(list)
    for ex in {e.exercise for s in counted(doc) for e in s.entries}:
        rows = [r for r in service.history(doc, ex) if r["e1rm"]]
        for i, r in enumerate(rows):
            start = (date.fromisoformat(r["date"]) - timedelta(days=WINDOW_DAYS)).isoformat()
            before = [p["e1rm"] for p in rows[:i] if start <= p["date"] < r["date"]]
            if before:
                by_session[r["session"]].append(r["e1rm"] / max(before) * 100)
    out = {}
    for s in counted(doc):
        found = by_session.get(s.id)
        day = service.day_of(s.started_at)
        if not found or s.deload or (since and day < since.isoformat()):
            continue
        at = coach.local(s.started_at)
        out[s.id] = {"date": day, "hour": at.hour if at else None, "score": round(sum(found) / len(found), 1)}
    return out


def _avg(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def findings(doc: GymDoc, health_days: list[dict[str, Any]] | None, today: date) -> dict[str, Any]:
    scored = scores(doc, today - timedelta(days=365))
    metrics = {d.get("date"): d.get("metrics") or {} for d in health_days or []}
    resting = [m["resting_heart_rate"] for m in metrics.values() if m.get("resting_heart_rate")]
    usual_rhr = median(resting) if resting else None

    def caffeine(m: dict[str, Any]) -> bool | None:
        if m.get("caffeine_mg") is not None:
            return m["caffeine_mg"] >= 100
        return False if any(k in m for k in ("water_ml", "alcohol_drinks")) else None

    tests = [
        ("sleep", lambda s, m: None if m.get("sleep_hours") is None else m["sleep_hours"] >= 7,
         "after 7 hours' sleep or more", "after less", "{a} sessions after a good night, {b} after a short one"),
        ("resting_hr", lambda s, m: None if usual_rhr is None or not m.get("resting_heart_rate") else m["resting_heart_rate"] <= usual_rhr,
         "when your resting heart rate is at or below your usual", "when it's up", "{a} sessions with it normal, {b} with it up"),
        ("morning", lambda s, m: None if s["hour"] is None else s["hour"] < 12,
         "before noon", "later in the day", "{a} morning sessions, {b} later"),
        ("caffeine", lambda s, m: caffeine(m),
         "on days with 100 mg of caffeine or more", "on days with less", "{a} sessions with caffeine, {b} without"),
    ]
    out = []
    for key, test, yes_text, no_text, counts in tests:
        yes, no = [], []
        for s in scored.values():
            got = test(s, metrics.get(s["date"]) or {})
            if got is not None:
                (yes if got else no).append(s["score"])
        if len(yes) < MIN_EACH_SIDE or len(no) < MIN_EACH_SIDE:
            continue
        a, b = _avg(yes), _avg(no)
        gap = a - b
        if abs(gap) < MIN_GAP:
            continue
        better = gap > 0
        text = (f"You lift about {abs(gap):.0f}% {'more' if better else 'less'} {yes_text} than {no_text}.")
        out.append({"key": key, "text": text, "gap": round(gap, 1), "with": round(a, 1), "without": round(b, 1),
                    "sessions": len(yes) + len(no), "counts": counts.format(a=len(yes), b=len(no))})
    out.sort(key=lambda f: -abs(f["gap"]))
    return {"findings": out, "scored": len(scored), "health": bool(metrics),
            "note": None if out else ("Not enough yet: it needs at least four sessions on each side of something, with your "
                                      "sleep and heart rate coming in from Apple Health." if len(scored) < 2 * MIN_EACH_SIDE or not metrics
                                      else "Nothing stands out yet: sleep, resting heart rate, time of day and caffeine all go with "
                                           "about the same lifting so far.")}
