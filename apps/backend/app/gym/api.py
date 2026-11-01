"""The gym (6.5). See service.py.

    GET    /api/v1/gym                       settings, exercises, routines, recent sessions, this week, streak
    PUT    /api/v1/gym/settings              {unit, bar, plates, increment, rest_s}
    POST   /api/v1/gym/exercises             your own exercise {name, primary, secondary, equipment, kind}
    DELETE /api/v1/gym/exercises/{id}
    GET    /api/v1/gym/exercises/{id}        its history, records, last time, and a chart series
    GET    /api/v1/gym/templates             starter routines
    POST   /api/v1/gym/routines              a routine (or {template: id} to copy one)
    PUT    /api/v1/gym/routines/{id}
    DELETE /api/v1/gym/routines/{id}
    GET    /api/v1/gym/plan?routine=&day=    a routine day ready to lift: last time and what to lift for each
    POST   /api/v1/gym/sessions              a finished session (same id again replaces it); returns its summary and records
    GET    /api/v1/gym/sessions?month=YYYY-MM
    GET    /api/v1/gym/sessions/{id}
    DELETE /api/v1/gym/sessions/{id}
    GET    /api/v1/gym/plates?weight=        the plates for each side
    GET    /api/v1/gym/warmups?exercise=&weight=&gym=   (6.7) warm-up sets up to a working weight
    GET    /api/v1/gym/heatmap?days=         (6.7) each day with a workout: volume, sets, main muscles
    POST   /api/v1/gym/import                (6.6) a JEFIT export or any CSV/zip: form `file`, `unit` (auto/kg/lb),
                                             `dry_run` (default true: a preview), `choices` (JSON: name -> exercise id or "new")
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.auth import require_user
from app.gym import importer, service, store, templates
from app.tasks import service as tasks

router = APIRouter(prefix="/api/v1/gym", tags=["gym"], dependencies=[Depends(require_user)])


def _missing(what: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"No such {what}.")


@router.get("")
def overview() -> dict[str, Any]:
    doc = store.load()
    today = tasks.today()
    active = next((r for r in doc.routines if r.active), None)
    return {
        "settings": doc.settings.model_dump(),
        "exercises": sorted(service.exercises(doc).values(), key=lambda e: e["name"]),
        "routines": [r.model_dump() for r in doc.routines],
        "active": {"routine": active.id, "next_day": service.next_day(doc, active.id)} if active else None,
        "recent": [service.summary(doc, s) for s in reversed(doc.sessions[-10:])],
        "week": service.week(doc, today),
        "streak_weeks": service.streak(doc, today),
        "total_sessions": len(doc.sessions),
    }


@router.put("/settings")
def put_settings(body: store.Settings) -> dict[str, Any]:
    doc = store.load()
    doc.settings = body
    store.save(doc)
    return body.model_dump()


@router.post("/exercises")
def add_exercise(body: store.CustomExercise) -> dict[str, Any]:
    from app.gym import library

    if body.primary not in library.MUSCLES or any(m not in library.MUSCLES for m in body.secondary):
        raise HTTPException(status_code=422, detail=f"Muscles are: {', '.join(library.MUSCLES)}.")
    doc = store.load()
    doc.exercises.append(body)
    store.save(doc)
    return body.model_dump()


@router.delete("/exercises/{exercise_id}")
def delete_exercise(exercise_id: str) -> dict[str, Any]:
    doc = store.load()
    before = len(doc.exercises)
    doc.exercises = [e for e in doc.exercises if e.id != exercise_id]
    if len(doc.exercises) == before:
        raise _missing("exercise of yours")
    store.save(doc)
    return {"deleted": exercise_id}


@router.get("/exercises/{exercise_id}")
def exercise(exercise_id: str) -> dict[str, Any]:
    doc = store.load()
    ex = service.exercises(doc).get(exercise_id)
    if ex is None:
        raise _missing("exercise")
    rows = service.history(doc, exercise_id)
    return {"exercise": ex, "records": service.records(rows), "last": rows[-1] if rows else None,
            "series": [{"date": r["date"], "e1rm": r["e1rm"], "best": r["best"].get("weight"), "volume": r["volume"], "reps": r["reps"]} for r in rows[-60:]],
            "history": list(reversed(rows[-30:]))}


@router.get("/templates")
def get_templates() -> dict[str, Any]:
    return {"templates": [t.model_dump() for t in templates.templates()]}


class NewRoutine(BaseModel):
    template: str | None = Field(default=None, max_length=40)
    routine: store.Routine | None = None


@router.post("/routines")
def add_routine(body: NewRoutine) -> dict[str, Any]:
    doc = store.load()
    if body.template:
        tpl = next((t for t in templates.templates() if t.id == body.template), None)
        if tpl is None:
            raise _missing("template")
        routine = tpl.model_copy(update={"id": store.new_id()})
    elif body.routine:
        routine = body.routine.model_copy(update={"id": store.new_id()})
    else:
        raise HTTPException(status_code=422, detail="Send a routine, or a template to copy.")
    if routine.active or not any(r.active for r in doc.routines):
        for r in doc.routines:
            r.active = False
        routine.active = True
    doc.routines.append(routine)
    store.save(doc)
    return routine.model_dump()


@router.put("/routines/{routine_id}")
def put_routine(routine_id: str, body: store.Routine) -> dict[str, Any]:
    doc = store.load()
    for i, r in enumerate(doc.routines):
        if r.id == routine_id:
            if body.active:
                for other in doc.routines:
                    other.active = False
            doc.routines[i] = body.model_copy(update={"id": routine_id})
            store.save(doc)
            return doc.routines[i].model_dump()
    raise _missing("routine")


@router.delete("/routines/{routine_id}")
def delete_routine(routine_id: str) -> dict[str, Any]:
    doc = store.load()
    kept = [r for r in doc.routines if r.id != routine_id]
    if len(kept) == len(doc.routines):
        raise _missing("routine")
    doc.routines = kept
    store.save(doc)
    return {"deleted": routine_id}


@router.get("/plan")
def plan(routine: str, day: int | None = Query(default=None, ge=0, le=13), gym: str | None = Query(default=None, max_length=40)) -> dict[str, Any]:
    doc = store.load()
    r = next((x for x in doc.routines if x.id == routine), None)
    if r is None or not r.days:
        raise _missing("routine")
    i = service.next_day(doc, r.id) if day is None else min(day, len(r.days) - 1)
    d = r.days[i]
    names = service.exercises(doc)
    out = []
    warmed: set[str] = set()
    for p in d.exercises:
        sug = service.suggest(doc, p, gym)
        ex = names.get(p.exercise, {})
        # Warm up for the first exercise that works each main muscle (6.7).
        warm = service.warmups(doc, p.exercise, sug.get("weight"), gym) if ex.get("primary") not in warmed else []
        if warm:
            warmed.add(ex.get("primary", ""))
        out.append({**p.model_dump(), "name": ex.get("name", p.exercise), "kind": ex.get("kind", "weight"), "equipment": ex.get("equipment"),
                    "last": service.last(doc, p.exercise), "suggest": sug, "warmups": warm})
    return {"routine": r.id, "day": i, "title": f"{r.name}: {d.name}", "gym": doc.settings.gym(gym).id, "exercises": out}


@router.get("/warmups")
def get_warmups(exercise: str = Query(max_length=60), weight: float = Query(gt=0, le=2000), gym: str | None = Query(default=None, max_length=40)) -> dict[str, Any]:
    return {"warmups": service.warmups(store.load(), exercise, weight, gym)}


@router.get("/heatmap")
def get_heatmap(days: int = Query(default=371, ge=7, le=3700)) -> dict[str, Any]:
    return {"days": service.heatmap(store.load(), tasks.today(), days)}


@router.post("/sessions")
def save_session(body: store.Session) -> dict[str, Any]:
    doc = store.load()
    doc.sessions = [s for s in doc.sessions if s.id != body.id]
    if not body.ended_at:
        body.ended_at = store.now()
    body.gym = body.gym or doc.settings.current_gym
    doc.sessions.append(body)
    store.save(doc)
    return {"summary": service.summary(doc, body), "records": service.new_records(doc, body)}


@router.get("/sessions")
def sessions(month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$")) -> dict[str, Any]:
    doc = store.load()
    picked = [s for s in doc.sessions if not month or s.started_at.startswith(month)]
    return {"sessions": [service.summary(doc, s) for s in reversed(picked)]}


@router.get("/sessions/{session_id}")
def session(session_id: str) -> dict[str, Any]:
    doc = store.load()
    s = next((x for x in doc.sessions if x.id == session_id), None)
    if s is None:
        raise _missing("session")
    names = service.exercises(doc)
    return {**s.model_dump(), "summary": service.summary(doc, s), "records": service.new_records(doc, s),
            "entries": [{**e.model_dump(), "name": names.get(e.exercise, {}).get("name", e.exercise)} for e in s.entries]}


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str) -> dict[str, Any]:
    doc = store.load()
    kept = [s for s in doc.sessions if s.id != session_id]
    if len(kept) == len(doc.sessions):
        raise _missing("session")
    doc.sessions = kept
    store.save(doc)
    return {"deleted": session_id}


@router.get("/plates")
def get_plates(weight: float = Query(ge=0, le=2000)) -> dict[str, Any]:
    s = store.load().settings
    return service.plates(weight, s.bar, s.plates)


@router.post("/import")
async def import_file(file: UploadFile = File(...), unit: str = Form("auto"), dry_run: bool = Form(True), choices: str = Form("{}")) -> dict[str, Any]:
    raw = await file.read()
    if len(raw) > 100_000_000:
        raise HTTPException(status_code=413, detail="That file is over 100 MB.")
    try:
        rows = importer.read_upload(raw, file.filename or "", unit if unit in ("kg", "lb") else None)
    except Exception as exc:  # a broken zip, a binary file
        raise HTTPException(status_code=422, detail=f"Couldn't read that file ({exc.__class__.__name__}).") from exc
    if not rows:
        raise HTTPException(status_code=422, detail="No workouts found. The file needs columns for a date and an exercise, "
                                                    "and either weight and reps, or sets written like 60x10,62.5x8.")
    doc = store.load()
    if dry_run:
        return {"preview": importer.preview(doc, rows)}
    try:
        picked = json.loads(choices or "{}")
    except ValueError:
        picked = {}
    return {"imported": importer.commit(doc, rows, {str(k): str(v) for k, v in picked.items()} if isinstance(picked, dict) else {})}
