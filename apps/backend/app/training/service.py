"""Training (5.5): a race, its plan, this week against it, and what to do
today, adjusted for how you've slept and recovered (Apple Health through
SirisAI). See plan.py for how the plan is made.

**Following what you did** (5.8): each planned run is matched with the runs
you actually did that day (SirisAI's workouts), so the week shows done and
missed. A tempo or long run missed in the last two days moves to today
when today is easy or free, instead of piling onto next week.

**Race prediction**: from your best recent effort (runs of 3 km or more in
the last six weeks), by Riegel's formula (time × (distance ratio)^1.06).

**Zones and paces**: heart-rate zones from the highest heart rate your
workouts have recorded in six months (50-60-70-80-90% of it); paces from the
predicted 10 km pace: easy and long about 25-30% slower, tempo about 5% slower.

**Readiness and getting sick** come from SirisAI (3.51): a Recover day eases
the session, a very low score or signs of illness mean rest.

**Recovery** compares last night with your own last 30 days: sleep more
than an hour under your usual, heart rate variability 20% or more under
it, or resting heart rate 5 bpm or more over it. One of those: today's
hard session becomes an easy one. Two or more: rest.

The plan is also a calendar you can subscribe to on your iPhone
(Settings → Calendar → Accounts → Add Subscribed Calendar), so each run
sits next to work.
"""

from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta, timezone
from statistics import mean
from typing import Any

from pydantic import BaseModel, Field

from app.hub import sirisai_api
from app.hub.service import Hub
from app.services import json_store
from app.tasks import service as tasks
from app.training import plan


class Race(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    distance_km: float = Field(gt=0.5, le=100)
    goal_time: str = Field(default="", max_length=20)
    start_km: float | None = Field(default=None, ge=0, le=300)  # your own starting week, if you'd rather


def _path():
    return json_store.data_path("SIRISOS_TRAINING_PATH", "training.json")


def _load() -> dict[str, Any]:
    doc = json_store.read(_path(), {})
    return doc if isinstance(doc, dict) else {}


def _save(doc: dict[str, Any]) -> None:
    json_store.write(_path(), doc)


def race() -> Race | None:
    raw = _load().get("race")
    return Race.model_validate(raw) if raw else None


def set_race(r: Race | None) -> None:
    doc = _load()
    doc["race"] = r.model_dump() if r else None
    _save(doc)


def feed_token() -> str:
    doc = _load()
    if not doc.get("feed"):
        doc["feed"] = secrets.token_urlsafe(24)
        _save(doc)
    return doc["feed"]


def new_feed_token() -> str:
    doc = _load()
    doc["feed"] = secrets.token_urlsafe(24)
    _save(doc)
    return doc["feed"]


async def health_days(hub: Hub, days: int = 42) -> list[dict[str, Any]] | None:
    body = await sirisai_api.get(hub, "/siris/hub/v1/health/days", params={"days": days})
    return None if body is None or body.get("days") is None else body["days"]


def recent_weekly_km(days: list[dict[str, Any]], today: date) -> float:
    start = plan.monday(today) - timedelta(weeks=4)
    total = sum(float((d.get("metrics") or {}).get("running_km") or 0) for d in days
                if start.isoformat() <= str(d.get("date")) < plan.monday(today).isoformat())
    return round(total / 4, 1)


def recovery(days: list[dict[str, Any]], today: date, ready: dict[str, Any] | None = None, sick: dict[str, Any] | None = None,
             energy: dict[str, Any] | None = None) -> dict[str, Any]:
    by = {str(d.get("date")): d.get("metrics") or {} for d in days}
    latest = by.get(today.isoformat()) or by.get((today - timedelta(days=1)).isoformat()) or {}
    since = (today - timedelta(days=31)).isoformat()
    history = [m for d, m in by.items() if since <= d < today.isoformat()]
    notes: list[str] = []

    def base(key: str) -> float | None:
        vals = [float(m[key]) for m in history if m.get(key)]
        return mean(vals) if len(vals) >= 5 else None

    # The HRV taken while asleep when there is one (SirisAI 3.62): the day's
    # average falls with every workout, so it can't judge the day's training.
    hrv_key = "hrv_overnight" if latest.get("hrv_overnight") and base("hrv_overnight") else "heart_rate_variability"
    sleep, hrv, rhr = latest.get("sleep_hours"), latest.get(hrv_key), latest.get("resting_heart_rate")
    if sleep and (b := base("sleep_hours")) and sleep <= b - 1:
        notes.append(f"You slept {sleep:.1f} h, {b - sleep:.1f} h under your usual")
    if hrv and (b := base(hrv_key)) and hrv <= b * 0.8:
        notes.append(f"HRV is {hrv:.0f} ms, well under your usual {b:.0f}")
    if rhr and (b := base("resting_heart_rate")) and rhr >= b + 5:
        notes.append(f"Resting heart rate is {rhr:.0f}, up from your usual {b:.0f}")
    level = "rest" if len(notes) >= 2 else "easy" if notes else "good"
    # SirisAI's readiness (3.51) and getting-sick warning can only make the day easier, never harder.
    order = ["good", "easy", "rest"]
    if ready:
        by_score = "rest" if ready["score"] < 30 else "easy" if ready["band"] == "Recover" else "good"
        if order.index(by_score) > order.index(level):
            level = by_score
            notes.append(f"Readiness {ready['score']}: {ready['summary']}")
    # Energy already spent today (6.1): a session still to come shouldn't be a hard one on an empty tank.
    if energy and energy.get("now") is not None and energy["now"] < 25 and level == "good":
        level = "easy"
        notes.append(f"Energy is down to {energy['now']} today")
    if sick:
        early = sick.get("level") == "early"
        if not early or level == "good":
            level = "easy" if early else "rest"
        notes.append(("Early signs you may be getting run down: " if early else "Signs you may be getting sick: ") + ", ".join(sick.get("today") or []))
    return {"level": level, "notes": notes, "known": bool(latest), "readiness": ready["score"] if ready else None}


def runs_by_day(workouts: list[dict[str, Any]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for w in workouts:
        if "run" in str(w.get("name") or "").lower() and w.get("km"):
            out[w["date"]] = round(out.get(w["date"], 0.0) + float(w["km"]), 2)
    return out


def predict(workouts: list[dict[str, Any]], distance_km: float, today: date) -> dict[str, Any] | None:
    since = (today - timedelta(weeks=6)).isoformat()
    best = None
    for w in workouts:
        km, minutes = w.get("km"), w.get("minutes")
        if "run" in str(w.get("name") or "").lower() and km and minutes and float(km) >= 3 and str(w.get("date")) >= since:
            t = float(minutes) * (distance_km / float(km)) ** 1.06
            if best is None or t < best[0]:
                best = (t, w)
    if best is None:
        return None
    t, w = best
    return {"minutes": round(t, 1), "time": _hms(t), "pace": _pace(t / distance_km),
            "from": f"{w['km']:g} km in {_hms(float(w['minutes']))} on {w['date']}"}


def zones(workouts: list[dict[str, Any]]) -> dict[str, Any] | None:
    top = max((float(w["max_hr"]) for w in workouts if w.get("max_hr")), default=None)
    if not top:
        return None
    bands = [("Zone 1, recovery", 0.5, 0.6), ("Zone 2, easy", 0.6, 0.7), ("Zone 3, steady", 0.7, 0.8),
             ("Zone 4, tempo", 0.8, 0.9), ("Zone 5, hard", 0.9, 1.0)]
    return {"max_hr": round(top), "zones": [{"name": n, "low": round(top * lo), "high": round(top * hi)} for n, lo, hi in bands]}


def paces(workouts: list[dict[str, Any]], today: date) -> dict[str, str] | None:
    p = predict(workouts, 10.0, today)
    if not p:
        return None
    per_km = p["minutes"] / 10
    return {"easy": _pace(per_km * 1.25), "long": _pace(per_km * 1.3), "tempo": _pace(per_km * 1.05), "ten_k": _pace(per_km)}


def _hms(minutes: float) -> str:
    total = round(minutes * 60)
    h, rest = divmod(total, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _pace(minutes_per_km: float) -> str:
    m, s = divmod(round(minutes_per_km * 60), 60)
    return f"{m}:{s:02d}/km"


def build(r: Race, days: list[dict[str, Any]] | None, today: date, workouts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    race_day = date.fromisoformat(r.date)
    if r.start_km is not None:
        start = r.start_km
    elif days is not None:
        start = recent_weekly_km(days, today)
    else:  # no health data to hand (the fitness card, the feed): the last start worked out
        start = float(_load().get("last_start") or 0)
    weeks = plan.weekly_targets(start, race_day, r.distance_km, today) if race_day >= today else []
    by = {str(d.get("date")): d.get("metrics") or {} for d in days or []}
    out_weeks = []
    for w in weeks:
        wk = date.fromisoformat(w["week_of"])
        runs = plan.sessions(w["km"], r.distance_km, wk, race_day)
        done = round(sum(float(by.get((wk + timedelta(days=i)).isoformat(), {}).get("running_km") or 0) for i in range(7)), 1)
        ran = runs_by_day(workouts or [])
        for s in runs:
            if s["date"] < today.isoformat() and s["kind"] in ("easy", "quality", "long"):
                km = ran.get(s["date"]) or float(by.get(s["date"], {}).get("running_km") or 0)
                s["status"] = "done" if km >= 0.6 * s["km"] else "partly" if km > 0 else "missed"
                s["done_km"] = round(km, 1)
        out_weeks.append({**w, "done_km": done if wk <= today else None, "sessions": runs})
    return {"race": r.model_dump(), "start_km": start, "days_to_go": (race_day - today).days, "weeks": out_weeks}


def today_session(built: dict[str, Any], rec: dict[str, Any], today: date) -> dict[str, Any] | None:
    sessions = [s for w in built["weeks"] for s in w["sessions"]]
    todays = next((dict(s) for s in sessions if s["date"] == today.isoformat() and s["kind"] in ("easy", "quality", "long", "race")), None)
    other = next((dict(s) for s in sessions if s["date"] == today.isoformat()), None)
    # A key session missed in the last two days moves to an easy or free today.
    recent = [s for s in sessions if s.get("status") == "missed" and s["kind"] in ("quality", "long")
              and (today - timedelta(days=2)).isoformat() <= s["date"] < today.isoformat()]
    if recent and (todays is None or todays["kind"] == "easy"):
        missed = recent[-1]
        todays = {**missed, "date": today.isoformat(), "moved_from": missed["date"],
                  "title": missed["title"] + f" (moved from {date.fromisoformat(missed['date']):%A})"}
    s = todays or other
    if s is None:
        return None
    if rec.get("notes"):
        s["why"] = "; ".join(rec["notes"])
    if s["kind"] in ("quality", "long") and rec["level"] == "easy":
        s.update(changed=True, title=f"Easy run, {max(3, round(s['km'] * 0.6)):g} km instead (recovery's down)")
    elif s["kind"] == "strength" and rec["level"] != "good":
        s.update(changed=True, title="Mobility only today, 20 min: recovery's down")
    elif s["kind"] != "race" and rec["level"] == "rest":
        s.update(changed=True, title="Rest today, or a gentle walk. Your body's asking for it.")
    return s


async def overview(hub: Hub, today: date | None = None) -> dict[str, Any]:
    today = today or tasks.today()
    from app.health import service as health

    r = race()
    days = await health_days(hub)
    workouts = await health.workouts(hub, 180)
    h = await health.overview(hub)
    rec = recovery(days or [], today, h.get("readiness"), h.get("getting_sick"), h.get("energy"))
    built = build(r, days, today, workouts) if r else None
    if built and days is not None and r and r.start_km is None:
        doc = _load()
        if doc.get("last_start") != built["start_km"]:
            doc["last_start"] = built["start_km"]
            _save(doc)
    this_week = next((w for w in (built or {}).get("weeks", []) if w["week_of"] == plan.monday(today).isoformat()), None)
    return {
        "today": today.isoformat(),
        "health": days is not None,
        "recovery": rec,
        "plan": built,
        "this_week": this_week,
        "session": today_session(built, rec, today) if built else None,
        "recent_weekly_km": recent_weekly_km(days or [], today),
        "prediction": predict(workouts, r.distance_km, today) if r else None,
        "zones": zones(workouts),
        "paces": paces(workouts, today),
    }


def week_target(today: date, days: list[dict[str, Any]] | None = None) -> float | None:
    """This week's planned km, for the fitness card's goal."""
    r = race()
    if not r or date.fromisoformat(r.date) < today:
        return None
    built = build(r, days, today)
    w = next((w for w in built["weeks"] if w["week_of"] == plan.monday(today).isoformat()), None)
    return w["km"] if w else None


def ics(today: date | None = None, days: list[dict[str, Any]] | None = None) -> str:
    """The plan as an iCalendar feed: an all-day event per run."""
    today = today or tasks.today()
    r = race()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SirisOS//Training//EN", "CALSCALE:GREGORIAN",
             "X-WR-CALNAME:Training (SirisOS)", "REFRESH-INTERVAL;VALUE=DURATION:PT6H"]
    if r:
        for w in build(r, days, today)["weeks"]:
            for s in w["sessions"]:
                d = date.fromisoformat(s["date"])
                lines += ["BEGIN:VEVENT", f"UID:sirisos-training-{s['date']}-{s['kind']}@sirisos", f"DTSTAMP:{stamp}",
                          f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"DTEND;VALUE=DATE:{d + timedelta(days=1):%Y%m%d}",
                          f"SUMMARY:{_escape(s['title'])}", "TRANSP:TRANSPARENT", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")
