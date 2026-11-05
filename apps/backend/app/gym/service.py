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

6.7:
- **Progression** per routine exercise: double (above), linear (add the
  increment every session you hit the reps; two misses in a row, back off
  10%), or percent (a share of your training max, 90% of your best estimated
  1RM in the last 90 days, one share per set).
- **Effort**: when every set hit the top and felt easy (average RPE 7 or
  less), add twice the increment; a miss that was a grind (RPE 9.5+) says so.
  Last time's note for the exercise comes back with the suggestion.
- **What the gym has**: a suggested weight is rounded to what the current
  gym can load: plates on the bar, the dumbbells on its rack, its machine
  stack step.
- **Warm-ups**: the empty bar for 10, then steps of the working weight
  (40% × 5, 60% × 3, 80% × 2 by default), each loadable.
- **Volume by muscle**: working sets this week, a set counting fully for the
  exercise's main muscle and half for each helper.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from app.gym import library
from app.gym.store import EntryLog, GymDoc, PlanExercise, Session, SetLog, counted, held

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


@lru_cache(maxsize=8192)
def _day(stamp: str) -> str:
    """The local date a session was on (6.8): the phone sends UTC, so a 7am
    workout in Melbourne used to be filed under the day before."""
    from app.gym.coach import local

    t = local(stamp) if ("Z" in stamp or "+" in stamp[10:] or stamp[19:20] == "-") else None
    return t.date().isoformat() if t else stamp[:10]


def day_of(stamp: str) -> str:
    return _day(stamp)


def history(doc: GymDoc, exercise: str) -> list[dict[str, Any]]:
    """Each session the exercise was in, oldest first."""
    out = []
    for s in counted(doc):
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
    """The records this session set, against every session before it. A deload session sets none (6.8)."""
    if session.deload:
        return []
    before = GymDoc(sessions=[s for s in counted(doc) if s.started_at < session.started_at and s.id != session.id])
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


def loadable(doc: GymDoc, exercise: str, weight: float, gym_id: str | None = None) -> float:
    """The nearest weight the gym can actually give you for this exercise."""
    gym = doc.settings.gym(gym_id)
    equipment = (exercises(doc).get(exercise) or {}).get("equipment", "")
    if equipment in ("barbell", "ez bar", "trap bar", "smith") and gym.plates:
        smallest = min(gym.plates) * 2
        return max(gym.bar, round(gym.bar + round((weight - gym.bar) / smallest) * smallest, 2))
    if equipment == "dumbbell" and gym.dumbbells:
        return min(gym.dumbbells, key=lambda d: (abs(d - weight), d))
    if equipment in ("machine", "cable") and gym.stack_step:
        return round(round(weight / gym.stack_step) * gym.stack_step, 2)
    return round(weight * 4) / 4


def training_max(doc: GymDoc, exercise: str, today: date | None = None) -> float | None:
    rows = history(doc, exercise)
    since = ((today or utcnow().date()) - timedelta(days=90)).isoformat()
    est = [r["e1rm"] for r in rows if r["e1rm"] and r["date"] >= since] or [r["e1rm"] for r in rows[-3:] if r["e1rm"]]
    return round(max(est) * 0.9, 1) if est else None


def _rpe(sets: list[dict[str, Any]]) -> float | None:
    vals = [x["rpe"] for x in sets if x.get("rpe")]
    return sum(vals) / len(vals) if vals else None


def suggest(doc: GymDoc, plan: PlanExercise, gym_id: str | None = None) -> dict[str, Any]:
    """What to lift for a routine's exercise today."""
    rows = history(doc, plan.exercise)
    prev = rows[-1]["sets"] if rows else []
    note = next((n for n in reversed([_note(doc, r["session"], plan.exercise) for r in rows[-3:]]) if n), None)
    lo, hi = rep_range(plan.reps)
    step = doc.settings.increment
    fit = lambda w: loadable(doc, plan.exercise, w, gym_id)  # noqa: E731
    out: dict[str, Any]
    if plan.progression == "percent":
        tm = training_max(doc, plan.exercise)
        shares = plan.percents or [0.75, 0.8, 0.85]
        if not tm:
            out = {"weight": None, "reps": hi, "why": "No estimated 1RM yet: do a session at a weight you could lift for the top of the range."}
        else:
            per_set = [fit(tm * p) for p in (shares * plan.sets)[:plan.sets]]
            out = {"weight": per_set[0], "reps": hi, "per_set": per_set, "training_max": tm,
                   "why": f"{', '.join(f'{p:.0%}' for p in shares[:plan.sets])} of your training max ({tm:g}, 90% of your best estimated 1RM)."}
        return {**out, "last_note": note}
    weights = [x["weight"] for x in prev if x.get("weight")]
    if not weights:
        return {"weight": None, "reps": hi, "why": "No history yet: pick a weight you could lift for the top of the range.", "last_note": note}
    top = max(weights)
    at_top = [x for x in prev if x.get("weight") == top]
    effort = _rpe(at_top)
    if plan.progression == "linear":
        hit = all((x.get("reps") or 0) >= lo for x in at_top)
        before = rows[-2]["sets"] if len(rows) > 1 else []
        missed_before = bool(before) and not all((x.get("reps") or 0) >= lo for x in before if x.get("weight") == max(
            (y.get("weight") or 0 for y in before), default=0))
        if hit:
            out = {"weight": fit(top + step), "reps": lo, "why": f"Every set at {top:g} reached {lo}: add {step:g}."}
        elif missed_before:
            out = {"weight": fit(top * 0.9), "reps": lo, "why": f"Missed {lo} at {top:g} twice: back off 10% and build again."}
        else:
            out = {"weight": top, "reps": lo, "why": f"Same as last time ({top:g}) until every set reaches {lo}."}
        return {**out, "last_note": note}
    hit = all((x.get("reps") or 0) >= hi for x in at_top)
    # The Watch's verdict on last time (7.1): effort 0-10 from heart rate (and RPE, where given) and the recovery between sets.
    w = _watch(doc, rows[-1]["session"], plan.exercise)
    hr = w.get("effort") if w else None
    if hit and effort is not None and effort <= 7:
        out = {"weight": fit(top + 2 * step), "reps": lo, "why": f"Every set at {top:g} reached {hi} and felt easy (RPE {effort:.1f}): add {2 * step:g}."}
    elif hit and effort is None and hr is not None and hr <= WATCH_EASY:
        out = {"weight": fit(top + 2 * step), "reps": lo,
               "why": f"Every set at {top:g} reached {hi} and your heart rate barely rose (effort {hr:g}/10 on the Watch): add {2 * step:g}."}
    elif hit and hr is not None and hr >= WATCH_HARD and (w.get("recovery_bpm") or 99) < 15:
        out = {"weight": top, "reps": hi,
               "why": f"Every set at {top:g} reached {hi}, but the Watch had you near your max (effort {hr:g}/10) and barely recovering between sets: "
                      "one more session here before adding."}
    elif hit:
        out = {"weight": fit(top + step), "reps": lo, "why": f"Last time every set at {top:g} reached {hi}: add {step:g}."}
    elif effort is not None and effort >= 9.5:
        out = {"weight": top, "reps": hi, "why": f"Same as last time ({top:g}): it was a grind (RPE {effort:.1f}), so own it before adding."}
    elif effort is None and hr is not None and hr >= WATCH_HARD:
        out = {"weight": top, "reps": hi, "why": f"Same as last time ({top:g}): the Watch says it was a grind (effort {hr:g}/10), so own it before adding."}
    else:
        out = {"weight": top, "reps": hi, "why": f"Same as last time ({top:g}) until every set reaches {hi}."}
    if hr is not None:
        out["watch_effort"] = hr
    return {**out, "last_note": note}


WATCH_EASY = 5.0
WATCH_HARD = 8.5


def _watch(doc: GymDoc, session_id: str, exercise: str) -> dict[str, Any] | None:
    s = next((x for x in doc.sessions if x.id == session_id), None)
    return (s.effort or {}).get(exercise) if s else None


def _note(doc: GymDoc, session_id: str, exercise: str) -> str | None:
    s = next((x for x in doc.sessions if x.id == session_id), None)
    e = next((e for e in (s.entries if s else []) if e.exercise == exercise), None)
    return (e.note or None) if e else None


def warmups(doc: GymDoc, exercise: str, target: float | None, gym_id: str | None = None) -> list[dict[str, Any]]:
    """Warm-up sets up to a working weight: the empty bar, then the settings' steps; ones too close to the bar or the work are left out."""
    st = doc.settings
    ex = exercises(doc).get(exercise) or {}
    if not st.warmups or not target or ex.get("kind", "weight") != "weight":
        return []
    gym = st.gym(gym_id)
    barbell = ex.get("equipment") in ("barbell", "ez bar", "trap bar", "smith")
    out: list[dict[str, Any]] = [{"weight": gym.bar, "reps": 10}] if barbell and target > gym.bar * 1.5 else []
    for step in st.warmup_steps:
        w = loadable(doc, exercise, target * step.percent, gym_id)
        if (barbell and w <= gym.bar) or w <= 0 or w >= target or any(abs(o["weight"] - w) < 1e-6 for o in out):
            continue
        out.append({"weight": w, "reps": step.reps})
    return out


def heatmap(doc: GymDoc, today: date, days: int = 371) -> list[dict[str, Any]]:
    """Each day with a workout in the last `days`: its volume, sets and the main muscles."""
    since = (today - timedelta(days=days)).isoformat()
    names = exercises(doc)
    out: dict[str, dict[str, Any]] = {}
    for s in counted(doc):
        d = _day(s.started_at)
        if d < since:
            continue
        cell = out.setdefault(d, {"date": d, "volume": 0.0, "sets": 0, "muscles": defaultdict(int)})
        for e in s.entries:
            n = len(working(e.sets))
            cell["volume"] += volume(e.sets)
            cell["sets"] += n
            if (m := (names.get(e.exercise) or {}).get("primary")) and n:
                cell["muscles"][m] += n
    return [{**c, "volume": round(c["volume"], 1), "muscles": [m for m, _ in sorted(c["muscles"].items(), key=lambda t: -t[1])][:3]}
            for c in sorted(out.values(), key=lambda c: c["date"])]


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
    sessions = [s for s in counted(doc) if _day(s.started_at) >= start]
    for s in sessions:
        for e in s.entries:
            n = len(working(e.sets))
            ex = names.get(e.exercise)
            if not ex or not n:
                continue
            by_muscle[ex["primary"]] += n
            for m in ex["secondary"]:
                by_muscle[m] += n * 0.5
    c = cardio(doc, sessions)
    return {"week_of": start, "sessions": len(sessions), "sets_by_muscle": {m: round(v, 1) for m, v in sorted(by_muscle.items(), key=lambda t: -t[1])},
            "volume": round(sum(volume(e.sets) for s in sessions for e in s.entries), 1), **c}


def cardio(doc: GymDoc, sessions: list[Session]) -> dict[str, Any]:
    """Conditioning in these workouts (7.1): minutes and km of the cardio and timed
    exercises (rower, bike, treadmill, circuits), and how many workouts had some."""
    names = exercises(doc)
    secs, km, n = 0, 0.0, 0
    for s in sessions:
        had = False
        for e in s.entries:
            if names.get(e.exercise, {}).get("kind") != "cardio":
                continue
            for x in e.sets:
                if x.done:
                    secs += x.seconds or 0
                    km += x.km or 0
                    had = had or bool(x.seconds or x.km)
        n += had
    return {"cardio_min": round(secs / 60), "cardio_km": round(km, 1), "cardio_sessions": n}


def streak(doc: GymDoc, today: date) -> int:
    """Weeks in a row (this one or last counting) with at least one session."""
    weeks = {date.fromisoformat(_day(s.started_at)).isocalendar()[:2] for s in counted(doc)}
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
            "names": [exercises(doc).get(e.exercise, {}).get("name", e.exercise) for e in s.entries][:8], "held": held(s)}


def trained_title(doc: GymDoc, entries: list[EntryLog]) -> str:
    """A workout's name from what was trained (7.0): the muscles with at least a
    fifth of the working sets, biggest first, at most three. "Chest and Back"."""
    names = exercises(doc)
    by_muscle: dict[str, int] = defaultdict(int)
    for e in entries:
        by_muscle[(names.get(e.exercise) or {}).get("primary") or "other"] += len(working(e.sets))
    total = sum(by_muscle.values())
    top = [m for m, n in sorted(by_muscle.items(), key=lambda t: -t[1]) if n and n >= total / 5 and m != "other"][:3]
    if not top:
        return "Workout"
    words = [m.capitalize() for m in top]
    return words[0] if len(words) == 1 else f"{', '.join(words[:-1])} and {words[-1]}"


WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def schedule(doc: GymDoc, routine_id: str, today: date) -> dict[str, Any] | None:
    """When a routine's days are on set weekdays (6.94): today's day (or a rest
    day) and the next one on. None when no day has a weekday, so the routine
    goes in turn as before."""
    r = next((x for x in doc.routines if x.id == routine_id), None)
    if not r or not any(d.weekdays for d in r.days):
        return None
    on = {wd: i for i, d in enumerate(r.days) for wd in d.weekdays}
    todays = on.get(today.weekday())
    nxt = None
    for k in range(1, 8):
        d = today + timedelta(days=k)
        if d.weekday() in on:
            nxt = {"day": on[d.weekday()], "date": d.isoformat(), "weekday": WEEKDAYS[d.weekday()]}
            break
    return {"today": todays, "rest": todays is None, "next": nxt,
            "week": [{"weekday": WEEKDAYS[w], "day": on.get(w), "name": r.days[on[w]].name if w in on else None} for w in range(7)]}


def next_day(doc: GymDoc, routine_id: str, today: date | None = None) -> int:
    """The routine day to do: today's when days are on set weekdays (the next
    one on, on a rest day), else the one after the last you did."""
    r = next((x for x in doc.routines if x.id == routine_id), None)
    if today is not None and (sched := schedule(doc, routine_id, today)):
        if sched["today"] is not None:
            return sched["today"]
        if sched["next"]:
            return sched["next"]["day"]
    done = [s.day for s in doc.sessions if s.routine_id == routine_id and s.day is not None]
    return 0 if not r or not r.days or not done else (done[-1] + 1) % len(r.days)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


CSV_COLUMNS = ["date", "started_at", "workout", "exercise", "exercise_id", "set", "type", "weight_kg", "reps", "seconds", "km", "rpe", "done_at", "note"]


def to_csv(doc: GymDoc) -> str:
    """Every set, one row each (7.1): kg, km and seconds."""
    import csv
    import io

    names = exercises(doc)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_COLUMNS)
    for s in doc.sessions:
        for e in s.entries:
            for i, x in enumerate(e.sets, 1):
                w.writerow([day_of(s.started_at), s.started_at, s.title, names.get(e.exercise, {}).get("name", e.exercise), e.exercise, i, x.type,
                            x.weight if x.weight is not None else "", x.reps if x.reps is not None else "", x.seconds if x.seconds is not None else "",
                            x.km if x.km is not None else "", x.rpe if x.rpe is not None else "", x.at or "", e.note if i == 1 else ""])
    return buf.getvalue()
