"""What the Watch says about each lift (7.1).

SirisAI lines the Watch's heart rate up with each set (gym_effort, 4.28) and
SirisOS keeps the verdict per exercise on the session (`Session.effort`), so
what to lift, the rest timer and the exercise page can use it without asking
SirisAI each time:

- **effort**: 0-10, heart rate's peak against your maximum, blended with RPE;
- **peak_hr / avg_hr**: across the exercise's working sets;
- **recovery_bpm**: how far heart rate came down before the next set;
- **settle_s**: how long after a set heart rate took to come halfway back down
  (from its peak to where it started), the basis of the learned rest;
- **top**: the heaviest working weight, so like can be compared with like.
"""

from __future__ import annotations

from statistics import median
from typing import Any

from app.gym import service
from app.gym.store import GymDoc, Session, counted

KEEP = ("effort", "peak_hr", "avg_hr", "recovery_bpm", "settle_s", "peak_share")
EASY = 5.0     # a Watch effort at or under this: the weight barely raised heart rate
HARD = 8.5     # at or over this: close to your maximum
MIN_REST, MAX_REST = 45, 300
SAME_WEIGHT_BPM = 5  # a peak this much lower at the same weight counts as fitter


def keep(s: Session, analysis: dict[str, Any]) -> bool:
    """Keep SirisAI's per-exercise verdict on the session. True when it changed."""
    if not analysis.get("linked"):
        return False
    out: dict[str, dict[str, float | None]] = {}
    names = {e.exercise for e in s.entries}
    for e in analysis.get("exercises") or []:
        key = e.get("id") or e.get("exercise")
        if key not in names:
            continue
        out[key] = {k: e.get(k) for k in KEEP}
    if out and out != s.effort:
        s.effort = out
        return True
    return False


def last_effort(doc: GymDoc, session_id: str, exercise: str) -> dict[str, Any] | None:
    s = next((x for x in doc.sessions if x.id == session_id), None)
    return (s.effort or {}).get(exercise) if s else None


def _top(s: Session, exercise: str) -> float | None:
    w = [x.weight for e in s.entries if e.exercise == exercise for x in service.working(e.sets) if x.weight]
    return max(w) if w else None


def rest(doc: GymDoc, exercise: str, planned: int) -> dict[str, Any] | None:
    """The rest your heart rate says this exercise needs: the middle of how long it
    took to settle after a set, over the last three linked sessions, to the next
    15 seconds. None until there's something to go on, or with learning off."""
    if not doc.settings.learn_rest:
        return None
    seen = [s.effort[exercise]["settle_s"] for s in reversed(counted(doc))
            if (s.effort or {}).get(exercise, {}).get("settle_s") is not None][:3]
    if not seen:
        return None
    mid = median(seen)
    secs = int(min(MAX_REST, max(MIN_REST, round(mid / 15) * 15)))
    if abs(secs - planned) < 15:
        return None
    n = len(seen)
    return {"seconds": secs, "planned": planned,
            "why": f"Your heart rate took about {round(mid)} s to settle after a set (last {n} workout{'s' if n > 1 else ''} with the Watch)."}


def fitness(doc: GymDoc, exercise: str) -> dict[str, Any] | None:
    """Fitter at the same weight: the weight you've lifted most often with the
    Watch on, and how the peak heart rate there compares, first time to latest."""
    rows = [(service.day_of(s.started_at), top, s.effort[exercise]) for s in counted(doc)
            if (s.effort or {}).get(exercise, {}).get("peak_hr") and (top := _top(s, exercise))]
    by: dict[float, list[tuple[str, dict[str, Any]]]] = {}
    for day, top, e in rows:
        by.setdefault(top, []).append((day, e))
    best = max((w for w in by if len(by[w]) >= 2), key=lambda w: (len(by[w]), w), default=None)
    if best is None:
        return None
    (d0, a), (d1, b) = by[best][0], by[best][-1]
    delta = round(b["peak_hr"] - a["peak_hr"])
    if delta <= -SAME_WEIGHT_BPM:
        verdict = "fitter"
        text = f"At {best:g} kg your heart rate peaks {-delta} bpm lower than on {d0} ({round(a['peak_hr'])} → {round(b['peak_hr'])} bpm): fitter at the same weight."
    elif delta >= SAME_WEIGHT_BPM:
        verdict = "harder"
        text = (f"At {best:g} kg your heart rate peaks {delta} bpm higher than on {d0} ({round(a['peak_hr'])} → {round(b['peak_hr'])} bpm): "
                "it's costing you more lately (sleep, recovery or a hard week can do that).")
    else:
        verdict = "same"
        text = f"At {best:g} kg your heart rate peaks about the same as on {d0} ({round(a['peak_hr'])} → {round(b['peak_hr'])} bpm)."
    return {"weight": best, "first": d0, "latest": d1, "times": len(by[best]), "first_peak": round(a["peak_hr"]), "latest_peak": round(b["peak_hr"]),
            "delta_bpm": delta, "verdict": verdict, "text": text,
            "series": [{"date": d, "peak_hr": round(e["peak_hr"]), "effort": e.get("effort")} for d, e in by[best]][-20:]}


def fitter(doc: GymDoc) -> list[str]:
    """Exercises where the same weight now costs noticeably less (or more), for SirisAI."""
    out = []
    ids = {e.exercise for s in counted(doc)[-40:] if s.effort for e in s.entries if e.exercise in s.effort}
    names = service.exercises(doc)
    for ex in sorted(ids):
        f = fitness(doc, ex)
        if f and f["verdict"] != "same":
            out.append(f"{names.get(ex, {}).get('name', ex)}: {f['text']}")
    return out[:6]


def pending(doc: GymDoc, today_iso: str, days: int = 14) -> list[Session]:
    """Recent workouts with set times that SirisAI hasn't given a verdict on yet."""
    from datetime import date, timedelta

    since = (date.fromisoformat(today_iso) - timedelta(days=days)).isoformat()
    return [s for s in doc.sessions if not s.effort and service.day_of(s.started_at) >= since
            and any(x.at for e in s.entries for x in e.sets)][-5:]
