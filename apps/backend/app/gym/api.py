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
    POST   /api/v1/gym/deload                (6.8) {on, days}: a deload week (half the sets, 10% lighter, no records)
    GET    /api/v1/gym/strength              (6.8) main lifts' best estimated 1RM against bodyweight
    GET    /api/v1/gym/year?year=            (6.8) the year in review
    POST   /api/v1/gym/builder               (6.9) a routine drafted from a goal ({text, days, goal, minutes, equipment, avoid})
    GET    /api/v1/gym/body                  (6.9) measurements, photos and the weight series (from SirisAI)
    POST   /api/v1/gym/measurements, DELETE /api/v1/gym/measurements/{id}
    POST   /api/v1/gym/photos (file, date, pose, note); GET/DELETE /api/v1/gym/photos/{id}
    POST   /api/v1/gym/rest {seconds, next}; DELETE /api/v1/gym/rest   (6.9) a push when the rest is over
    GET    /api/v1/gym/swap?exercise=&gym=   (6.93) other exercises for the same job
    GET    /api/v1/gym/sessions/{id}/effort  (6.96) the Watch's heart rate lined up with each set, from SirisAI
    GET    /api/v1/gym/duplicates; POST /api/v1/gym/merge {source, into}   (7.0) exercises that look the same, and merging one into the other
    POST   /api/v1/gym/sessions/{id}/review {verdict}   (7.0) an imported day too big to be one workout: real, wrong, or not looked at yet
    GET    /api/v1/gym/morning               (7.0) today's plan for the morning card
    GET    /api/v1/gym/coach                 (7.0) the week's one or two changes, from SirisAI
    GET    /api/v1/gym/protein               (6.93) today's protein against a target from bodyweight
    POST   /api/v1/gym/schedule {day, minutes, dry_run}   (6.93) a free slot for the gym, then into the calendar
  6.8 also: the overview has sets per muscle against targets, a deload suggestion and today's readiness;
  /plan adjusts for readiness and a deload week; a saved session goes to SirisAI for strain; a session
  shows the Apple Watch workout that overlaps it.
    POST   /api/v1/gym/import                (6.6) a JEFIT export or any CSV/zip: form `file`, `unit` (auto/kg/lb),
                                             `dry_run` (default true: a preview), `choices` (JSON: name -> exercise id or "new")
"""

from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

import asyncio
import logging
import time

from app.auth import require_user
from app.gym import builder, coach, importer, service, store, templates, tidy, watch
from app.hub import sirisai_api
from app.hub.service import Hub, get_hub
from app.tasks import service as tasks

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/gym", tags=["gym"], dependencies=[Depends(require_user)])


def _missing(what: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"No such {what}.")


HEALTH_FRESH_S = 300
_health_saved: tuple[float, dict[str, Any]] | None = None
_health_refresh: asyncio.Task | None = None


async def _health(hub: Hub) -> dict[str, Any]:
    """_read_health, kept for five minutes (7.0): SirisAI works out 70 days of scores for it (about 2 s), and
    nearly every gym page wants it. Once it's old, the saved answer is served while a new one is fetched behind it."""
    global _health_saved, _health_refresh

    async def fetch() -> dict[str, Any]:
        global _health_saved
        found = await _read_health(hub)
        if found:
            _health_saved = (time.monotonic(), found)
        return found

    if _health_saved is None:
        return await fetch()
    at, saved = _health_saved
    if time.monotonic() - at > HEALTH_FRESH_S and (_health_refresh is None or _health_refresh.done()):
        _health_refresh = asyncio.create_task(fetch())
    return saved


async def _read_health(hub: Hub) -> dict[str, Any]:
    """Today's readiness, the last few mornings and the latest weight, from SirisAI (6.8); nothing when it can't be reached."""
    from app.health import service as health

    async def scored() -> dict[str, Any]:
        try:
            return await asyncio.wait_for(health.overview(hub), timeout=6)
        except Exception:  # noqa: BLE001 - the gym works without it
            return {}

    async def weighed() -> list[dict[str, Any]] | None:
        try:
            return await asyncio.wait_for(health.weights(hub), timeout=8)
        except Exception:  # noqa: BLE001
            return None

    # 7.91: weight comes from the daily records, not the overview: the overview can take longer than the gym waits
    # (and then there was no weight at all), and it only looks 70 days back.
    body, series = await asyncio.gather(scored(), weighed())
    weight = (body.get("weight") or {}) if isinstance(body.get("weight"), dict) else {}
    if series:
        latest, latest_date = series[-1]["weight"], series[-1]["date"]
    else:
        latest, latest_date = weight.get("latest") or weight.get("current") or weight.get("kg"), weight.get("latest_date")
        series = weight.get("series") or []
    if not body and not series:
        return {}
    return {"readiness": body.get("readiness"), "recent": body.get("readiness_recent") or [],
            "weight_kg": latest, "weight_date": latest_date, "weight_series": series[-60:]}


def _low(h: dict[str, Any]) -> int:
    return sum(1 for r in (h.get("recent") or [])[-5:] if (r or {}).get("band") == "Recover")


@router.get("")
async def overview(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    doc = store.load()
    today = tasks.today()
    h = await _health(hub)
    active = next((r for r in doc.routines if r.active), None)
    return {
        "settings": doc.settings.model_dump(),
        "exercises": sorted(service.exercises(doc).values(), key=lambda e: e["name"]),
        "routines": [r.model_dump() for r in doc.routines],
        "active": {"routine": active.id, "next_day": service.next_day(doc, active.id, today),
                   "schedule": service.schedule(doc, active.id, today)} if active else None,
        "recent": [service.summary(doc, s) for s in reversed(doc.sessions[-10:])],
        "week": service.week(doc, today),
        "streak_weeks": service.streak(doc, today),
        "total_sessions": len(store.counted(doc)),
        "held": [service.summary(doc, s) for s in reversed(doc.sessions) if store.held(s) and not s.review],
        "muscles": coach.muscles(doc, today),
        "deload": coach.deload(doc, today, _low(h)),
        "niggles": [n.model_dump() for n in coach.active_niggles(doc)],
        "readiness": {k: (h.get("readiness") or {}).get(k) for k in ("score", "band")} if h.get("readiness") else None,
    }


class DeloadRequest(BaseModel):
    on: bool = True
    days: int = Field(default=7, ge=1, le=14)


@router.post("/deload")
def set_deload(body: DeloadRequest) -> dict[str, Any]:
    """Start (or end) a deload week: half the sets, 10% lighter, no records."""
    from datetime import timedelta

    doc = store.load()
    doc.settings.deload_until = (tasks.today() + timedelta(days=body.days - 1)).isoformat() if body.on else None
    store.save(doc)
    return coach.deload(doc, tasks.today())


@router.get("/strength")
async def strength(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    h = await _health(hub)
    return coach.standards(store.load(), tasks.today(), h.get("weight_kg"))


@router.get("/year")
def year_review(year: int | None = Query(default=None, ge=2000, le=2100)) -> dict[str, Any]:
    return coach.year(store.load(), year or tasks.today().year)


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
            "history": list(reversed(rows[-30:])), "fitness": watch.fitness(doc, exercise_id),
            "videos": [v.model_dump(exclude={"file"}) for v in sorted(doc.videos, key=lambda v: v.date, reverse=True) if v.exercise == exercise_id]}


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
async def plan(routine: str, day: int | None = Query(default=None, ge=0, le=13), gym: str | None = Query(default=None, max_length=40),
               hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    doc = await _refresh_effort(hub, store.load())
    h = await _health(hub)
    deloading = coach.deload(doc, tasks.today())["active"]
    r = next((x for x in doc.routines if x.id == routine), None)
    if r is None or not r.days:
        raise _missing("routine")
    i = service.next_day(doc, r.id, tasks.today()) if day is None else min(day, len(r.days) - 1)
    d = r.days[i]
    names = service.exercises(doc)
    out = []
    warmed: set[str] = set()
    for p in d.exercises:
        spared = coach.spare(doc, p.exercise, gym)  # a sore spot (7.1): swap to something that spares it
        if spared and spared["swap"]:
            p = p.model_copy(update={"exercise": spared["swap"]})
        sets, sug = coach.adjust(p, service.suggest(doc, p, gym), doc, h.get("readiness"), deloading)
        ex = names.get(p.exercise, {})
        learned = watch.rest(doc, p.exercise, p.rest_s)  # the rest your heart rate needs (7.1)
        extra: dict[str, Any] = {}
        if spared:
            extra["niggle"] = {**spared, "from": d.exercises[len(out)].exercise if spared["swap"] else None}
        if learned:
            extra["rest_learned"] = learned
        # Warm up for the first exercise that works each main muscle (6.7).
        warm = service.warmups(doc, p.exercise, sug.get("weight"), gym) if ex.get("primary") not in warmed else []
        if warm:
            warmed.add(ex.get("primary", ""))
        out.append({**p.model_dump(), "sets": sets, "name": ex.get("name", p.exercise), "kind": ex.get("kind", "weight"), "equipment": ex.get("equipment"),
                    "last": service.last(doc, p.exercise), "suggest": sug, "warmups": warm, **extra,
                    **({"rest_s": learned["seconds"]} if learned else {})})
    band = (h.get("readiness") or {}).get("band")
    return {"routine": r.id, "day": i, "title": f"{r.name}: {d.name}", "gym": doc.settings.gym(gym).id, "exercises": out, "deload": deloading,
            "readiness": {"score": (h.get("readiness") or {}).get("score"), "band": band} if band else None}


@router.get("/warmups")
def get_warmups(exercise: str = Query(max_length=60), weight: float = Query(gt=0, le=2000), gym: str | None = Query(default=None, max_length=40)) -> dict[str, Any]:
    return {"warmups": service.warmups(store.load(), exercise, weight, gym)}


@router.get("/heatmap")
def get_heatmap(days: int = Query(default=371, ge=7, le=3700)) -> dict[str, Any]:
    return {"days": service.heatmap(store.load(), tasks.today(), days)}


async def _send_session(hub: Hub, doc: store.GymDoc, s: store.Session) -> None:
    """The session with each set's time goes to SirisAI (6.96), which links it to the Watch workout and works out the effort."""
    if not any(x.at for e in s.entries for x in e.sets):
        return
    try:
        await sirisai_api.post(hub, "/siris/health/gym/session", json=coach.timeline(doc, s), timeout=8.0)
    except Exception as exc:  # noqa: BLE001
        log.info("Couldn't send the session to SirisAI: %s", exc)


async def _send_day(hub: Hub, doc: store.GymDoc, day: str) -> None:
    """The day's gym sessions go to SirisAI as workouts (6.8), so strain and the training load count them,
    and a training summary (6.9) so chat and voice can answer about it."""
    try:
        await sirisai_api.post(hub, "/siris/health/metrics", json=coach.as_workouts(doc, day), headers={"X-Health-Source": "sirisgym"}, timeout=8.0)
        await sirisai_api.post(hub, "/siris/health/gym", json=coach.for_sirisai(doc, tasks.today()), timeout=8.0)
    except Exception as exc:  # noqa: BLE001 - the workout is saved either way
        log.info("Couldn't send the gym day to SirisAI: %s", exc)


@router.post("/sessions")
async def save_session(body: store.Session, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    doc = store.load()
    was = next((s for s in doc.sessions if s.id == body.id), None)
    if was and was.effort and not body.effort:
        body.effort = was.effort  # the Watch's verdict is kept on the server; the phone doesn't send it back
    doc.sessions = [s for s in doc.sessions if s.id != body.id]
    if not body.ended_at:
        body.ended_at = store.now()
    body.gym = body.gym or doc.settings.current_gym
    doc.sessions.append(body)
    store.save(doc)
    await _send_day(hub, doc, service.day_of(body.started_at))
    await _send_session(hub, doc, body)
    return {"summary": service.summary(doc, body), "records": service.new_records(doc, body)}


@router.get("/sessions")
def sessions(month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$")) -> dict[str, Any]:
    doc = store.load()
    picked = [s for s in doc.sessions if not month or service.day_of(s.started_at).startswith(month)]
    return {"sessions": [service.summary(doc, s) for s in reversed(picked)]}


@router.get("/sessions/{session_id}")
async def session(session_id: str, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    from app.health import service as health

    doc = store.load()
    s = next((x for x in doc.sessions if x.id == session_id), None)
    if s is None:
        raise _missing("session")
    names = service.exercises(doc)
    try:
        watch = coach.watch_for(s, await asyncio.wait_for(health.workouts(hub, 400), timeout=6))
    except Exception:  # noqa: BLE001
        watch = None
    return {**s.model_dump(), "summary": service.summary(doc, s), "records": service.new_records(doc, s), "watch": watch,
            "entries": [{**e.model_dump(), "name": names.get(e.exercise, {}).get("name", e.exercise)} for e in s.entries]}


class ReviewRequest(BaseModel):
    verdict: Literal["", "real", "wrong"]


@router.post("/sessions/{session_id}/review")
async def review_session(session_id: str, body: ReviewRequest, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    """Your call on an imported day too big to be one workout. It's never deleted: "real" counts it, "wrong" keeps it out."""
    doc = store.load()
    s = next((x for x in doc.sessions if x.id == session_id), None)
    if s is None:
        raise _missing("session")
    s.review = body.verdict
    store.save(doc)
    doc = store.load()  # worked out afresh, with the new verdict
    await _send_day(hub, doc, service.day_of(s.started_at))  # what SirisAI goes by follows your call
    return {"id": session_id, "review": body.verdict, "left": sum(1 for x in doc.sessions if store.held(x) and not x.review)}


@router.get("/duplicates")
def duplicates() -> dict[str, Any]:
    return {"duplicates": tidy.duplicates(store.load())}


class MergeRequest(BaseModel):
    source: str = Field(max_length=60)
    into: str = Field(max_length=60)


@router.post("/merge")
def merge(body: MergeRequest) -> dict[str, Any]:
    """Merge one of your exercises into another; a copy of the file is kept first."""
    doc = store.load()
    try:
        out = tidy.merge(doc, body.source, body.into)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    store.backup("before-merge")
    store.save(doc)
    return out


@router.get("/coach")
async def weekly_coach(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    """The week's one or two changes, from SirisAI (training, sleep, recovery, protein). Nothing when it isn't connected."""
    return await sirisai_api.get(hub, "/siris/health/gym/coach", timeout=15.0) or {"changes": [], "enough": False, "text": ""}


@router.get("/morning")
async def morning(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    """The morning card: today's workout and readiness, and what it takes to start it."""
    doc = store.load()
    today = tasks.today()
    h = await _health(hub)
    readiness = h.get("readiness")
    plan = coach.today_for_brief(doc, today, readiness)
    active = next((r for r in doc.routines if r.active), None)
    if not plan or not active:
        return {"plan": None}
    return {"plan": plan, "routine": active.id, "day": service.next_day(doc, active.id, today), "gym": doc.settings.current_gym,
            "shortcut": doc.settings.shortcut_start, "readiness": {k: (readiness or {}).get(k) for k in ("score", "band")} if readiness else None}


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
async def import_file(file: UploadFile = File(...), unit: str = Form("auto"), dry_run: bool = Form(True), choices: str = Form("{}"),
                      skip_logged: bool = Form(True)) -> dict[str, Any]:
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
    return {"imported": importer.commit(doc, rows, {str(k): str(v) for k, v in picked.items()} if isinstance(picked, dict) else {}, skip_logged)}


@router.post("/cleanup")
def cleanup(dry_run: bool = Query(default=False)) -> dict[str, Any]:
    """Take out exercises with nothing logged (6.95): empty entries in workouts, and your own exercises with no data
    that no routine uses. Workouts themselves are kept; a copy of gym.json is saved first."""
    doc = store.load()
    out = store.clean_empty(doc)
    if not dry_run and (out["entries_removed"] or out["exercises_removed"]):
        store.backup("before-cleanup")
        store.save(doc)
    return {**out, "dry_run": dry_run}



# -- 6.9: the programme builder, body measurements, progress photos, the rest timer on the lock screen --

@router.post("/builder")
def build_programme(body: builder.BuildRequest) -> dict[str, Any]:
    """A routine drafted from a goal, to edit and save (it isn't saved here)."""
    return builder.build(body)


@router.get("/body")
async def body(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    doc = store.load()
    h = await _health(hub)
    return {"measurements": [m.model_dump() for m in sorted(doc.measurements, key=lambda m: m.date)],
            "photos": [p.model_dump(exclude={"file"}) for p in sorted(doc.photos, key=lambda p: p.date)],
            "weight": [{"date": w.get("date"), "kg": w.get("weight"), "trend": w.get("trend")} for w in h.get("weight_series") or []]}


@router.post("/measurements")
def add_measurement(m: store.Measurement) -> dict[str, Any]:
    doc = store.load()
    doc.measurements = [x for x in doc.measurements if x.id != m.id]
    doc.measurements.append(m)
    store.save(doc)
    return m.model_dump()


@router.delete("/measurements/{measurement_id}")
def delete_measurement(measurement_id: str) -> dict[str, Any]:
    doc = store.load()
    kept = [x for x in doc.measurements if x.id != measurement_id]
    if len(kept) == len(doc.measurements):
        raise _missing("measurement")
    doc.measurements = kept
    store.save(doc)
    return {"deleted": measurement_id}


PHOTO_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/heic": "heic", "image/heif": "heic"}
MAX_PHOTO = 20 * 1024 * 1024


@router.post("/photos")
async def add_photo(file: UploadFile = File(...), date: str = Form(..., pattern=r"^\d{4}-\d{2}-\d{2}$"), pose: str = Form("front"),
                    note: str = Form("", max_length=200)) -> dict[str, Any]:
    ext = PHOTO_TYPES.get((file.content_type or "").lower())
    if not ext:
        raise HTTPException(status_code=415, detail="Send a JPEG, PNG, WebP or HEIC photo.")
    raw = await file.read(MAX_PHOTO + 1)
    if len(raw) > MAX_PHOTO:
        raise HTTPException(status_code=413, detail="That photo is over 20 MB.")
    photo = store.Photo(date=date, pose=pose if pose in ("front", "side", "back") else "other", note=note, file="")
    photo.file = f"{photo.id}.{ext}"
    (store.photo_dir() / photo.file).write_bytes(raw)
    doc = store.load()
    doc.photos.append(photo)
    store.save(doc)
    return photo.model_dump(exclude={"file"})


@router.get("/photos/{photo_id}")
def get_photo(photo_id: str) -> FileResponse:
    p = next((x for x in store.load().photos if x.id == photo_id), None)
    path = store.photo_dir() / p.file if p else None
    if p is None or path is None or not path.is_file():
        raise _missing("photo")
    return FileResponse(path, headers={"Cache-Control": "private, max-age=86400"})


@router.delete("/photos/{photo_id}")
def delete_photo(photo_id: str) -> dict[str, Any]:
    doc = store.load()
    p = next((x for x in doc.photos if x.id == photo_id), None)
    if p is None:
        raise _missing("photo")
    (store.photo_dir() / p.file).unlink(missing_ok=True)
    doc.photos = [x for x in doc.photos if x.id != photo_id]
    store.save(doc)
    return {"deleted": photo_id}


class RestRequest(BaseModel):
    seconds: int = Field(ge=5, le=900)
    next: str = Field(default="", max_length=120)


_rest: dict[str, asyncio.Task] = {}


async def _ring(seconds: int, text: str) -> None:
    from app.push import notifier

    await asyncio.sleep(seconds)
    await notifier.deliver([notifier.message(f"gym-rest-{store.new_id()}", "gym", "Rest's over", text or "Next set.", url="/gym/workout", urgency="high")])


@router.post("/rest")
async def start_rest(body: RestRequest) -> dict[str, Any]:
    """A push when the rest is over (6.9), so the phone can be locked between sets. A new rest replaces the last."""
    if (old := _rest.pop("current", None)) is not None:
        old.cancel()
    _rest["current"] = asyncio.create_task(_ring(body.seconds, body.next))
    return {"ringing_in": body.seconds}


@router.delete("/rest")
async def stop_rest() -> dict[str, Any]:
    if (old := _rest.pop("current", None)) is not None:
        old.cancel()
        return {"stopped": True}
    return {"stopped": False}



# -- 6.93: swap an exercise, protein, a gym slot in the calendar --

@router.get("/swap")
def swap(exercise: str = Query(max_length=60), gym: str | None = Query(default=None, max_length=40)) -> dict[str, Any]:
    return {"options": coach.swaps(store.load(), exercise, gym)}


@router.get("/protein")
async def protein(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    """Today's protein against a target from your bodyweight (Apple Health, via SirisAI) and whether you trained."""
    h = await _health(hub)
    eaten = None
    try:
        body = await asyncio.wait_for(sirisai_api.get(hub, "/siris/hub/v1/health/days", params={"days": 1}), timeout=6)
        today = tasks.today().isoformat()
        for d in (body or {}).get("days") or []:
            if str(d.get("date")) == today:
                m = d.get("metrics") or {}
                vals = [m.get("protein_g"), m.get("meal_protein_g_estimate")]
                eaten = max((float(v) for v in vals if v is not None), default=None)
    except Exception:  # noqa: BLE001
        pass
    return coach.protein(store.load(), tasks.today(), h.get("weight_kg"), eaten)


class ScheduleRequest(BaseModel):
    day: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    minutes: int = Field(default=60, ge=15, le=180)
    title: str = Field(default="", max_length=80)
    dry_run: bool = True


@router.post("/schedule")
async def schedule(body: ScheduleRequest, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    """A gym slot in the calendar (6.93): the first free gap that day (early, lunch, after work, then any time),
    shown first (dry_run) and added on a second tap, through SirisAI's calendar."""
    from datetime import date as date_type, timedelta as td

    from app.calendar import service as calendar
    from app.health import service as health

    doc = store.load()
    day = date_type.fromisoformat(body.day) if body.day else tasks.today()
    got = await calendar.events(hub, day, day + td(days=1))
    if got.get("events") is None:
        raise HTTPException(status_code=502, detail="Couldn't read the calendar from SirisAI.")
    slot = coach.free_slot(got["events"], day, body.minutes)
    if slot is None:
        return {"slot": None, "detail": f"No free {body.minutes} minutes on {day.isoformat()} between 6am and 9pm."}
    active = next((r for r in doc.routines if r.active), None)
    title = body.title or (f"Gym: {active.days[service.next_day(doc, active.id, day)].name}" if active and active.days else "Gym")
    out = {"slot": {"start": slot[0].isoformat(timespec="minutes"), "end": slot[1].isoformat(timespec="minutes")}, "title": title}
    if body.dry_run:
        return out
    result = await health.tool(hub, "calendar_create_event", {"summary": title, "start": slot[0].isoformat(), "end": slot[1].isoformat()})
    return {**out, "added": True, "result": result}



@router.get("/sessions/{session_id}/effort")
async def session_effort(session_id: str, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    """The Watch's heart rate lined up with each set, and the effort per exercise, from SirisAI (6.96, SirisAI 4.28)."""
    doc = store.load()
    s = next((x for x in doc.sessions if x.id == session_id), None)
    if s is None:
        raise _missing("session")
    if not any(x.at for e in s.entries for x in e.sets):
        return {"linked": False, "why": "This workout has no set times (it was imported, or logged before 6.96), so it can't be lined up with the Watch."}
    body = await sirisai_api.get(hub, f"/siris/health/gym/session/{session_id}/analysis", timeout=15.0)
    if body is None:
        return {"linked": False, "why": "SirisAI didn't answer (it needs 4.28 or later)."}
    if not body.get("linked") and "hasn't had this workout" in str(body.get("why")):
        await _send_session(hub, doc, s)  # sent again (it may have been saved offline, or before SirisAI was updated)
        body = await sirisai_api.get(hub, f"/siris/health/gym/session/{session_id}/analysis", timeout=15.0) or body
    if watch.keep(s, body):
        store.save(doc)
    return body


_TRIED: dict[str, float] = {}


async def _refresh_effort(hub: Hub, doc: store.GymDoc) -> store.GymDoc:
    """Ask SirisAI about recent workouts it hasn't given a verdict on (7.1), at most
    every half hour each, so what to lift and the rest timer use the Watch."""
    changed = False
    for s in watch.pending(doc, tasks.today().isoformat()):
        if time.monotonic() - _TRIED.get(s.id, -1e9) < 1800:
            continue
        _TRIED[s.id] = time.monotonic()
        try:
            body = await sirisai_api.get(hub, f"/siris/health/gym/session/{s.id}/analysis", timeout=6.0)
        except Exception:  # noqa: BLE001
            body = None
        if body and watch.keep(s, body):
            changed = True
    if changed:
        store.save(doc)
    return doc


@router.post("/effort/refresh")
async def refresh_effort(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    doc = await _refresh_effort(hub, store.load())
    return {"waiting": len(watch.pending(doc, tasks.today().isoformat()))}


# -- 7.1: niggles, form videos, backups and export --

class NiggleRequest(BaseModel):
    area: Literal["shoulder", "elbow", "wrist", "lower back", "knee"]
    note: str = Field(default="", max_length=200)


@router.get("/niggles")
def niggles() -> dict[str, Any]:
    doc = store.load()
    return {"niggles": [n.model_dump() for n in reversed(doc.niggles)], "areas": store.AREAS}


@router.post("/niggles")
def add_niggle(body: NiggleRequest) -> dict[str, Any]:
    doc = store.load()
    n = next((x for x in doc.niggles if x.area == body.area and not x.healed), None)
    if n:
        n.note = body.note or n.note
    else:
        n = store.Niggle(area=body.area, note=body.note, started=tasks.today().isoformat())
        doc.niggles.append(n)
    store.save(doc)
    return n.model_dump()


@router.post("/niggles/{niggle_id}/healed")
def heal_niggle(niggle_id: str) -> dict[str, Any]:
    doc = store.load()
    n = next((x for x in doc.niggles if x.id == niggle_id), None)
    if n is None:
        raise _missing("niggle")
    n.healed = tasks.today().isoformat()
    store.save(doc)
    return n.model_dump()


VIDEO_TYPES = {"video/mp4": "mp4", "video/quicktime": "mov", "video/webm": "webm", "video/x-m4v": "m4v"}
VIDEO_MAX = 300 * 1024 * 1024


@router.post("/videos")
async def add_video(file: UploadFile = File(...), exercise: str = Form(..., max_length=60), session: str | None = Form(None),
                    set: int | None = Form(None), weight: float | None = Form(None), reps: int | None = Form(None),
                    note: str = Form("", max_length=200), date: str | None = Form(None)) -> dict[str, Any]:
    ext = VIDEO_TYPES.get((file.content_type or "").lower())
    if not ext:
        raise HTTPException(status_code=415, detail="Send an MP4, MOV or WebM video.")
    v = store.Video(date=date or tasks.today().isoformat(), exercise=exercise, session=session, set=set, weight=weight, reps=reps,
                    note=note, file="", type=file.content_type or "video/mp4")
    v.file = f"{v.id}.{ext}"
    path = store.video_dir() / v.file
    size = 0
    with path.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > VIDEO_MAX:
                out.close()
                path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="That video is over 300 MB: trim it to the set.")
            out.write(chunk)
    doc = store.load()
    doc.videos.append(v)
    store.save(doc)
    return v.model_dump(exclude={"file"})


@router.get("/videos")
def videos(exercise: str | None = Query(default=None, max_length=60)) -> dict[str, Any]:
    doc = store.load()
    return {"videos": [v.model_dump(exclude={"file"}) for v in sorted(doc.videos, key=lambda v: v.date, reverse=True)
                       if exercise is None or v.exercise == exercise]}


@router.get("/videos/{video_id}")
def get_video(video_id: str) -> FileResponse:
    v = next((x for x in store.load().videos if x.id == video_id), None)
    path = store.video_dir() / v.file if v else None
    if path is None or not path.exists():
        raise _missing("video")
    return FileResponse(path, media_type=v.type)


@router.delete("/videos/{video_id}")
def delete_video(video_id: str) -> dict[str, Any]:
    doc = store.load()
    v = next((x for x in doc.videos if x.id == video_id), None)
    if v is None:
        raise _missing("video")
    (store.video_dir() / v.file).unlink(missing_ok=True)
    doc.videos = [x for x in doc.videos if x.id != video_id]
    store.save(doc)
    return {"deleted": video_id}


@router.get("/backups")
def list_backups() -> dict[str, Any]:
    return {"backups": store.backups()}


class RestoreRequest(BaseModel):
    name: str = Field(max_length=80)


@router.post("/backups/restore")
def restore_backup(body: RestoreRequest) -> dict[str, Any]:
    if body.name not in {b["name"] for b in store.backups()}:
        raise _missing("backup")
    try:
        return store.restore(body.name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/export.csv")
def export_csv() -> Response:
    """Every set ever logged, one row each, in kg, km and seconds (7.1)."""
    return Response(service.to_csv(store.load()), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="sirisgym-{tasks.today().isoformat()}.csv"'})


@router.get("/export.json")
def export_json() -> Response:
    doc = store.load()
    return Response(doc.model_dump_json(indent=1), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="sirisgym-{tasks.today().isoformat()}.json"'})
