"""SirisGYM's smarter training (6.8): weekly sets per muscle against a target,
when to deload, today's readiness in the plan, strength against bodyweight,
the year in review, and the Apple Watch workout that matches a session.

- **Muscle targets**: working sets a week per muscle (a helper muscle counts
  half), against a range (10-20 by default; change any in settings). Under or
  over says so.
- **Deload**: suggested when the main lifts have stalled (no better estimated
  1RM in their last three sessions), after six or more weeks of training in a
  row without a lighter week, or when readiness has been low on three of the
  last five mornings. A deload week halves the sets and takes 10% off.
- **Readiness**: a Recover morning takes a set off each exercise (not below
  two) and 5% off the weight; a Primed one says it's a good day to push.
- **Strength standards**: the best estimated 1RM of the main lifts as a
  multiple of bodyweight, with a rough level. The levels are broad rules of
  thumb for adult lifters, not a judgement.
- **Year in review**: sessions, hours, sets, volume, records by month, the
  most-trained muscles and the best lift of each main exercise, against the
  year before.
- **Watch match**: the Apple Health workout (from SirisAI) that overlaps a
  session gives it heart rate and energy, and stops the gym session counting
  twice in strain.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from app.gym import service
from app.gym.store import GymDoc, PlanExercise, Session

MUSCLE_TARGET = (10.0, 20.0)
MAIN_LIFTS = {"back-squat": "Squat", "bench-press": "Bench press", "deadlift": "Deadlift", "overhead-press": "Overhead press",
              "barbell-row": "Barbell row", "pull-up": "Pull-up"}
# Broad bodyweight multiples for an estimated 1RM: beginner, novice, intermediate, advanced.
STANDARDS = {"back-squat": (0.75, 1.25, 1.5, 2.0), "bench-press": (0.5, 0.75, 1.0, 1.5), "deadlift": (1.0, 1.5, 2.0, 2.5),
             "overhead-press": (0.35, 0.55, 0.75, 1.0), "barbell-row": (0.5, 0.75, 1.0, 1.25), "pull-up": (0.0, 0.1, 0.35, 0.65)}
LEVELS = ["starting out", "beginner", "novice", "intermediate", "advanced"]


def muscles(doc: GymDoc, today: date) -> list[dict[str, Any]]:
    week = service.week(doc, today)["sets_by_muscle"]
    targets = doc.settings.muscle_targets or {}
    from app.gym import library

    out = []
    for m in library.MUSCLES:
        if m in ("cardio", "full body"):
            continue
        lo, hi = (targets.get(m) or MUSCLE_TARGET)[:2]
        n = week.get(m, 0.0)
        out.append({"muscle": m, "sets": n, "target": [lo, hi], "status": "under" if n < lo else "over" if n > hi else "in range"})
    return out


def _stalled(doc: GymDoc) -> list[str]:
    names = service.exercises(doc)
    out = []
    for ex in MAIN_LIFTS:
        rows = [r for r in service.history(doc, ex) if r["e1rm"]]
        if len(rows) < 4:
            continue
        best_before = max(r["e1rm"] for r in rows[:-3])
        if max(r["e1rm"] for r in rows[-3:]) <= best_before:
            out.append(names.get(ex, {}).get("name", ex))
    return out


def weeks_in_a_row(doc: GymDoc, today: date) -> int:
    """Weeks in a row with training and no deload session."""
    by_week: dict[tuple[int, int], bool] = {}
    for s in doc.sessions:
        k = date.fromisoformat(service.day_of(s.started_at)).isocalendar()[:2]
        by_week[k] = by_week.get(k, False) or s.deload
    d = today - timedelta(days=today.weekday())
    n = 0
    while (k := d.isocalendar()[:2]) in by_week and not by_week[k]:
        n += 1
        d -= timedelta(days=7)
    return n


def deload(doc: GymDoc, today: date, low_mornings: int = 0) -> dict[str, Any]:
    active = bool(doc.settings.deload_until and doc.settings.deload_until >= today.isoformat())
    why = []
    if stalled := _stalled(doc):
        why.append(f"{', '.join(stalled)} {'has' if len(stalled) == 1 else 'have'} stalled for three sessions")
    if (n := weeks_in_a_row(doc, today)) >= 6:
        why.append(f"{n} weeks of training in a row without a lighter week")
    if low_mornings >= 3:
        why.append(f"readiness has been low on {low_mornings} of the last five mornings")
    return {"active": active, "until": doc.settings.deload_until if active else None, "suggest": bool(why) and not active, "why": why}


def adjust(plan: PlanExercise, sug: dict[str, Any], doc: GymDoc, readiness: dict[str, Any] | None, deloading: bool) -> tuple[int, dict[str, Any]]:
    """Sets and the suggestion after a deload week or today's readiness."""
    sets = plan.sets
    fit = lambda w: service.loadable(doc, plan.exercise, w)  # noqa: E731
    if deloading:
        sets = max(1, (plan.sets + 1) // 2)
        if sug.get("weight"):
            sug = {**sug, "weight": fit(sug["weight"] * 0.9), "per_set": [fit(w * 0.9) for w in sug.get("per_set") or []] or None,
                   "why": f"Deload week: half the sets and 10% lighter. {sug['why']}"}
        return sets, sug
    band = (readiness or {}).get("band")
    if band == "Recover":
        sets = max(2, plan.sets - 1) if plan.sets > 2 else plan.sets
        if sug.get("weight"):
            sug = {**sug, "weight": fit(sug["weight"] * 0.95), "per_set": [fit(w * 0.95) for w in sug.get("per_set") or []] or None,
                   "why": f"Readiness is low today ({(readiness or {}).get('score', '?')}): a set fewer and 5% lighter. {sug['why']}"}
    elif band == "Primed" and sug.get("weight"):
        sug = {**sug, "push": True, "why": f"{sug['why']} You're primed today: a good day to go for an extra rep or a record."}
    return sets, sug


def bodyweight(doc: GymDoc, weight_kg: float | None = None) -> float | None:
    """The latest bodyweight: from Apple Health (via SirisAI) when given, else the last one logged with a session."""
    if weight_kg:
        return weight_kg
    logged = [s.bodyweight for s in doc.sessions if s.bodyweight]
    return logged[-1] if logged else None


def standards(doc: GymDoc, today: date, weight_kg: float | None = None) -> dict[str, Any]:
    bw = bodyweight(doc, weight_kg)
    names = service.exercises(doc)
    out = []
    for ex, label in MAIN_LIFTS.items():
        rows = [r for r in service.history(doc, ex) if r["e1rm"]]
        if not rows:
            continue
        best = max(rows, key=lambda r: r["e1rm"])
        year = [r["e1rm"] for r in rows if r["date"][:4] == str(today.year)]
        last_year = [r["e1rm"] for r in rows if r["date"][:4] == str(today.year - 1)]
        value = best["e1rm"] + (bw if ex == "pull-up" and bw else 0)  # a pull-up lifts you too
        ratio = round(value / bw - (1 if ex == "pull-up" else 0), 2) if bw else None
        level = None
        if ratio is not None:
            level = LEVELS[sum(1 for t in STANDARDS[ex] if ratio >= t)]
        out.append({"exercise": ex, "name": names.get(ex, {}).get("name", label), "best": best["e1rm"], "date": best["date"],
                    "this_year": max(year) if year else None, "last_year": max(last_year) if last_year else None,
                    "ratio": ratio, "level": level})
    return {"bodyweight": bw, "lifts": out}


def year(doc: GymDoc, y: int) -> dict[str, Any]:
    def stats(yy: int) -> dict[str, Any]:
        ss = [s for s in doc.sessions if service.day_of(s.started_at)[:4] == str(yy)]
        minutes = sum(service.summary(doc, s)["minutes"] or 0 for s in ss)
        return {"sessions": len(ss), "hours": round(minutes / 60, 1), "sets": sum(service.summary(doc, s)["sets"] for s in ss),
                "volume": round(sum(service.summary(doc, s)["volume"] for s in ss), 1)}

    names = service.exercises(doc)
    months = [{"month": f"{y}-{m:02d}", "sessions": 0, "volume": 0.0, "records": 0} for m in range(1, 13)]
    by_muscle: dict[str, float] = defaultdict(float)
    prior = GymDoc(exercises=doc.exercises, settings=doc.settings)
    for s in sorted(doc.sessions, key=lambda x: x.started_at):
        d = service.day_of(s.started_at)
        if d[:4] == str(y):
            m = months[int(d[5:7]) - 1]
            m["sessions"] += 1
            m["volume"] = round(m["volume"] + service.summary(doc, s)["volume"], 1)
            if not s.deload:
                m["records"] += len([r for r in service.new_records(GymDoc(exercises=doc.exercises, sessions=[*prior.sessions, s]), s)
                                     if r["kind"] in ("heaviest", "e1rm")])
            for e in s.entries:
                n = len(service.working(e.sets))
                if (ex := names.get(e.exercise)) and n:
                    by_muscle[ex["primary"]] += n
        prior.sessions.append(s)
    best = []
    for ex in MAIN_LIFTS:
        rows = [r for r in service.history(doc, ex) if r["e1rm"] and r["date"][:4] == str(y)]
        if rows:
            r = max(rows, key=lambda t: t["e1rm"])
            best.append({"exercise": ex, "name": names.get(ex, {}).get("name", ex), "e1rm": r["e1rm"], "date": r["date"]})
    return {"year": y, **stats(y), "previous": stats(y - 1), "months": months,
            "muscles": [{"muscle": m, "sets": n} for m, n in sorted(by_muscle.items(), key=lambda t: -t[1])][:6], "best": best}


def _aware(stamp: str | None) -> datetime | None:
    """A time with its offset ("2026-11-01 07:00:00 +1100", "2026-10-31T20:00:00Z"); one without is taken as local."""
    from app.tasks.service import zone

    if not stamp:
        return None
    text = str(stamp).strip().replace("T", " ").replace("Z", "+0000")
    for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S.%f%z"):
        try:
            return datetime.strptime(text.replace("+00:00", "+0000"), fmt)
        except ValueError:
            continue
    try:
        t = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=zone())


def local(stamp: str) -> datetime | None:
    from app.tasks.service import zone

    t = _aware(stamp)
    return t.astimezone(zone()) if t else None


def watch_for(s: Session, workouts: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The Apple Health workout that overlaps this session (it starts from 20 minutes before the session to its end)."""
    start = _aware(s.started_at)
    if start is None:
        return None
    end = start + timedelta(minutes=max(20, service.summary(GymDoc(), s)["minutes"] or 60))
    best, gap = None, None
    for w in workouts:
        t = _aware(w.get("start"))
        if w.get("source") == "sirisgym" or t is None:
            continue
        if start - timedelta(minutes=20) <= t <= end and (gap is None or abs((t - start).total_seconds()) < gap):
            best, gap = w, abs((t - start).total_seconds())
    if not best:
        return None
    return {"name": best.get("name"), "start": best.get("start"), "minutes": best.get("minutes"), "avg_hr": best.get("avg_hr"),
            "max_hr": best.get("max_hr"), "kj": round(best["kcal"] * 4.184) if best.get("kcal") else None}


def for_sirisai(doc: GymDoc, today: date) -> dict[str, Any]:
    """What SirisAI needs to answer about training (6.9): recent workouts, each
    main lift's trend, this week by muscle, records in the last 30 days, the
    deload state and the next routine day with what to lift."""
    names = service.exercises(doc)
    recent = [service.summary(doc, s) for s in doc.sessions[-8:]]
    lifts = {}
    for ex, label in MAIN_LIFTS.items():
        rows = [r for r in service.history(doc, ex) if r["e1rm"]]
        if rows:
            lifts[names.get(ex, {}).get("name", label)] = {"best": max(r["e1rm"] for r in rows),
                                                          "last": [{"date": r["date"], "e1rm": r["e1rm"], "top": r["best"].get("weight")} for r in rows[-6:]]}
    since = (today - timedelta(days=30)).isoformat()
    records = []
    for s in doc.sessions:
        if service.day_of(s.started_at) >= since:
            records += [r["text"] for r in service.new_records(doc, s)]
    active = next((r for r in doc.routines if r.active), None)
    nxt = None
    if active and active.days:
        i = service.next_day(doc, active.id)
        d = active.days[i]
        nxt = {"routine": active.name, "day": d.name, "exercises": [
            {"name": names.get(p.exercise, {}).get("name", p.exercise), "sets": p.sets, "reps": p.reps, **{k: v for k, v in service.suggest(doc, p).items() if k in ("weight", "why")}}
            for p in d.exercises]}
    return {"today": today.isoformat(), "total_sessions": len(doc.sessions), "streak_weeks": service.streak(doc, today), "recent": recent,
            "lifts": lifts, "week": service.week(doc, today), "muscles": [m for m in muscles(doc, today) if m["status"] != "in range"],
            "records_30d": records[-12:], "deload": deload(doc, today), "next": nxt,
            "measurements": [m.model_dump(exclude={"id"}) for m in doc.measurements[-3:]]}


def as_workouts(doc: GymDoc, day: str) -> dict[str, Any]:
    """A day's gym sessions in SirisAI's own shape, for strain and the training load."""
    items = []
    for s in doc.sessions:
        t = local(s.started_at)
        if t is None or t.date().isoformat() != day:
            continue
        summ = service.summary(doc, s)
        items.append({"name": f"SirisGYM: {s.title}"[:60], "start": t.strftime("%Y-%m-%d %H:%M:%S %z"), "minutes": summ["minutes"] or 45,
                      "km": None, "kcal": None, "avg_hr": None, "max_hr": None})
    return {"metrics": {day: {}}, "workouts": {day: items}}
