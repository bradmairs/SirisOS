"""Gym logic (6.5): one-rep max, records, the last time you did something,
what to lift next, plates, and the week's volume by muscle.

- **Estimated 1RM**: Epley, weight × (1 + reps / 30); a single is itself.
  Only sets of 12 reps or fewer count, where the estimate holds.
- **Records** per exercise: heaviest weight, best estimated 1RM, the heaviest
  for 1, 3, 5 and 10 reps, the most reps in a set, and the biggest session
  (volume = weight × reps over the working sets). A finished session says
  which records it set.
- **What next** for a routine's exercise: the last session's working sets;
  if every one reached the top of the rep range, add the increment (2.5 kg),
  otherwise the same weight again.
- **Plates**: per side, largest first, from the plates you have.
- **Volume by muscle**: working sets this week, a set counting fully for the
  exercise's main muscle and half for each helper.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.gym import library
from app.gym.store import GymDoc, PlanExercise, Session, SetLog

REP_MAXES = (1, 3, 5, 10)


def exercises(doc: GymDoc) -> dict[str, dict[str, Any]]:
    return {**library.BUILTIN, **{e.id: e.model_dump() for e in doc.exercises}}


def e1rm(weight: float | None, reps: int | None) -> float | None:
    if not weight or not reps or reps > 12:
        return None
    return round(weight if reps == 1 else weight * (1 + reps / 30), 1)


def working(sets: list[SetLog]) -> list[SetLog]:
    return [s for s in sets if s.done and s.type != "warmup"]


def volume(sets: list[SetLog]) -> float:
    return round(sum((s.weight or 0) * (s.reps or 0) for s in working(sets)), 1)


def _day(stamp: str) -> str:
    return stamp[:10]


def history(doc: GymDoc, exercise: str) -> list[dict[str, Any]]:
    """Each session the exercise was in, oldest first."""
    out = []
    for s in doc.sessions:
        for e in s.entries:
            if e.exercise != exercise or not working(e.sets):
                continue
            ws = working(e.sets)
            best = max(ws, key=lambda x: ((x.weight or 0), (x.reps or 0)))
            est = [v for x in ws if (v := e1rm(x.weight, x.reps))]
            out.append({"session": s.id, "date": _day(s.started_at), "sets": [x.model_dump() for x in ws], "best": best.model_dump(),
                        "e1rm": max(est) if est else None, "volume": volume(e.sets), "reps": sum(x.reps or 0 for x in ws),
                        "seconds": sum(x.seconds or 0 for x in ws), "km": round(sum(x.km or 0 for x in ws), 2)})
    return out


def records(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sets = [(r["date"], x) for r in rows for x in r["sets"]]
    out: dict[str, Any] = {}
    weighted = [(d, x) for d, x in sets if x.get("weight")]
    if weighted:
        d, x = max(weighted, key=lambda t: (t[1]["weight"], t[1].get("reps") or 0))
        out["heaviest"] = {"weight": x["weight"], "reps": x.get("reps"), "date": d}
    est = [(r["date"], r["e1rm"]) for r in rows if r["e1rm"]]
    if est:
        d, v = max(est, key=lambda t: t[1])
        out["e1rm"] = {"value": v, "date": d}
    out["rep_max"] = {}
    for n in REP_MAXES:
        fit = [(d, x) for d, x in weighted if (x.get("reps") or 0) >= n]
        if fit:
            d, x = max(fit, key=lambda t: t[1]["weight"])
            out["rep_max"][str(n)] = {"weight": x["weight"], "date": d}
    reps = [(d, x) for d, x in sets if x.get("reps")]
    if reps:
        d, x = max(reps, key=lambda t: t[1]["reps"])
        out["most_reps"] = {"reps": x["reps"], "weight": x.get("weight"), "date": d}
    if rows and max(r["volume"] for r in rows) > 0:
        r = max(rows, key=lambda t: t["volume"])
        out["best_volume"] = {"volume": r["volume"], "date": r["date"]}
    return out


def new_records(doc: GymDoc, session: Session) -> list[dict[str, Any]]:
    """The records this session set, against every session before it."""
    before = GymDoc(sessions=[s for s in doc.sessions if s.started_at < session.started_at and s.id != session.id])
    names = exercises(doc)
    found = []
    for e in session.entries:
        if not working(e.sets):
            continue
        old = records(history(before, e.exercise))
        new = records(history(GymDoc(sessions=[*before.sessions, session]), e.exercise))
        name = names.get(e.exercise, {}).get("name", e.exercise)
        if not history(before, e.exercise):
            continue  # a first time isn't a record
        if (new.get("heaviest") or {}).get("weight", 0) > (old.get("heaviest") or {}).get("weight", 0):
            found.append({"exercise": e.exercise, "name": name, "kind": "heaviest", "text": f"{name}: heaviest ever, {new['heaviest']['weight']:g}"})
        if (new.get("e1rm") or {}).get("value", 0) > (old.get("e1rm") or {}).get("value", 0):
            found.append({"exercise": e.exercise, "name": name, "kind": "e1rm", "text": f"{name}: best estimated 1RM, {new['e1rm']['value']:g}"})
        if (new.get("best_volume") or {}).get("volume", 0) > (old.get("best_volume") or {}).get("volume", 0):
            found.append({"exercise": e.exercise, "name": name, "kind": "volume", "text": f"{name}: biggest session, {new['best_volume']['volume']:g}"})
        for n, v in (new.get("rep_max") or {}).items():
            if v["weight"] > ((old.get("rep_max") or {}).get(n) or {}).get("weight", 0) and n != "1":
                found.append({"exercise": e.exercise, "name": name, "kind": f"{n}rm", "text": f"{name}: best for {n} reps, {v['weight']:g}"})
    return found


def last(doc: GymDoc, exercise: str, before: str | None = None) -> list[dict[str, Any]]:
    rows = [r for r in history(doc, exercise) if before is None or r["date"] < before]
    return rows[-1]["sets"] if rows else []


def rep_range(reps: str) -> tuple[int, int]:
    lo, _, hi = reps.partition("-")
    return int(lo), int(hi or lo)


def suggest(doc: GymDoc, plan: PlanExercise) -> dict[str, Any]:
    """What to lift for a routine's exercise today."""
    prev = last(doc, plan.exercise)
    lo, hi = rep_range(plan.reps)
    weights = [x["weight"] for x in prev if x.get("weight")]
    if not weights:
        return {"weight": None, "reps": hi, "why": "No history yet: pick a weight you could lift for the top of the range."}
    top = max(weights)
    hit = all((x.get("reps") or 0) >= hi for x in prev if x.get("weight") == top)
    step = doc.settings.increment
    if hit:
        return {"weight": round(top + step, 2), "reps": lo, "why": f"Last time every set at {top:g} reached {hi}: add {step:g}."}
    return {"weight": top, "reps": hi, "why": f"Same as last time ({top:g}) until every set reaches {hi}."}


def plates(target: float, bar: float, available: list[float]) -> dict[str, Any]:
    per_side = (target - bar) / 2
    if per_side < 0:
        return {"per_side": [], "left": round(target - bar, 2), "loaded": bar}
    out = []
    rest = per_side
    for p in sorted(available, reverse=True):
        while rest >= p - 1e-9:
            out.append(p)
            rest -= p
    loaded = bar + 2 * sum(out)
    return {"per_side": out, "left": round(rest * 2, 2), "loaded": round(loaded, 2)}


def week(doc: GymDoc, today: date) -> dict[str, Any]:
    start = (today - timedelta(days=today.weekday())).isoformat()
    names = exercises(doc)
    by_muscle: dict[str, float] = defaultdict(float)
    sessions = [s for s in doc.sessions if _day(s.started_at) >= start]
    for s in sessions:
        for e in s.entries:
            n = len(working(e.sets))
            ex = names.get(e.exercise)
            if not ex or not n:
                continue
            by_muscle[ex["primary"]] += n
            for m in ex["secondary"]:
                by_muscle[m] += n * 0.5
    return {"week_of": start, "sessions": len(sessions), "sets_by_muscle": {m: round(v, 1) for m, v in sorted(by_muscle.items(), key=lambda t: -t[1])},
            "volume": round(sum(volume(e.sets) for s in sessions for e in s.entries), 1)}


def streak(doc: GymDoc, today: date) -> int:
    """Weeks in a row (this one or last counting) with at least one session."""
    weeks = {date.fromisoformat(_day(s.started_at)).isocalendar()[:2] for s in doc.sessions}
    d = today - timedelta(days=today.weekday())
    if d.isocalendar()[:2] not in weeks:
        d -= timedelta(days=7)
    n = 0
    while d.isocalendar()[:2] in weeks:
        n += 1
        d -= timedelta(days=7)
    return n


def summary(doc: GymDoc, s: Session) -> dict[str, Any]:
    minutes = None
    if s.ended_at:
        minutes = round((datetime.fromisoformat(s.ended_at) - datetime.fromisoformat(s.started_at)).total_seconds() / 60)
    sets = sum(len(working(e.sets)) for e in s.entries)
    return {"id": s.id, "title": s.title, "date": _day(s.started_at), "started_at": s.started_at, "minutes": minutes, "sets": sets,
            "exercises": len([e for e in s.entries if working(e.sets)]), "volume": round(sum(volume(e.sets) for e in s.entries), 1),
            "names": [exercises(doc).get(e.exercise, {}).get("name", e.exercise) for e in s.entries][:8]}


def next_day(doc: GymDoc, routine_id: str) -> int:
    """The routine day after the last one you did."""
    r = next((x for x in doc.routines if x.id == routine_id), None)
    done = [s.day for s in doc.sessions if s.routine_id == routine_id and s.day is not None]
    return 0 if not r or not r.days or not done else (done[-1] + 1) % len(r.days)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
