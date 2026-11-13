"""Mental health (9.1): mood and mindful minutes from Apple Health, by way of
SirisAI, beside what you keep here: journal entries (gratitude, a reframed
thought, a note), time spent on the calming tools, and Clarity.

Mood comes two ways: Apple Health's State of Mind (a valence, -1 to 1, read by
SirisAI 6.18 as `mood_valence`) and SirisOS's own 1-5 quick log (`mood`). Both
are put on one scale for the chart and the patterns: valence, where 1-5 maps
to -1..1.

Clarity is a private streak for a habit you're stepping away from: the day it
started, check-ins, urges (what set them off, and whether you rode them out),
your reasons and your plan. It's kept only here, in mind.json: never sent to
SirisAI, never in search, notifications or "Ask about this page".
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any

from app.services import json_store
from app.brief.service import zone
from app.tasks.service import today

MAX_JOURNAL = 2000
MAX_SESSIONS = 3000
MAX_URGES = 3000


def _path():
    return json_store.data_path("SIRISOS_MIND_PATH", "mind.json")


def load() -> dict[str, Any]:
    doc = json_store.read(_path(), {})
    doc.setdefault("journal", [])
    doc.setdefault("sessions", [])
    c = doc.setdefault("clarity", {})
    c.setdefault("start", None)
    c.setdefault("best", 0)
    c.setdefault("resets", [])
    c.setdefault("checks", {})  # day -> "clear" | "slip"
    c.setdefault("urges", [])
    c.setdefault("reasons", [])
    c.setdefault("plan", [])
    c.setdefault("nudge", False)
    doc.setdefault("habits", [])
    return doc


def save(doc: dict[str, Any]) -> None:
    json_store.write(_path(), doc)


def _now() -> str:
    return datetime.now(zone()).isoformat(timespec="seconds")


def _id() -> str:
    return uuid.uuid4().hex[:12]


# -- mood ----------------------------------------------------------------------------------------------------------

def valence(metrics: dict[str, Any]) -> float | None:
    """The day's mood on one scale (-1..1): Apple's State of Mind, else the 1-5 quick log."""
    v = metrics.get("mood_valence")
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    m = metrics.get("mood")
    if isinstance(m, (int, float)) and 1 <= m <= 5:
        return round((float(m) - 3) / 2, 2)
    return None


def word(v: float | None) -> str | None:
    """Apple's seven bands, in words."""
    if v is None:
        return None
    for top, w in ((-0.715, "Very unpleasant"), (-0.43, "Unpleasant"), (-0.143, "Slightly unpleasant"), (0.143, "Neutral"),
                   (0.43, "Slightly pleasant"), (0.715, "Pleasant")):
        if v < top:
            return w
    return "Very pleasant"


def _avg(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 2) if xs else None


def patterns(days: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What goes with a better mood, from your own days: sleep, exercise, mindful minutes, daylight. Each needs at least
    four days on each side, and a difference worth saying (0.15 on the -1..1 scale)."""
    out = []
    by_date = {d["date"]: d for d in days}

    def split(name: str, test, text_yes: str, text_no: str) -> None:
        yes, no = [], []
        for d in days:
            v = d.get("valence")
            if v is None:
                continue
            got = test(d, by_date)
            if got is None:
                continue
            (yes if got else no).append(v)
        if len(yes) >= 4 and len(no) >= 4:
            a, b = _avg(yes), _avg(no)
            if a is not None and b is not None and abs(a - b) >= 0.15:
                better = a > b
                out.append({"key": name, "text": f"Your mood is {'better' if better else 'lower'} {text_yes} than {text_no}.",
                            "with": a, "without": b, "days": len(yes) + len(no)})

    def night_before(d: dict[str, Any], by: dict[str, Any]):
        h = d.get("sleep_hours")
        return None if h is None else h >= 7

    split("sleep", night_before, "after 7 hours' sleep or more", "after less")
    split("exercise", lambda d, _: None if d.get("exercise_minutes") is None else d["exercise_minutes"] >= 30, "on days with 30 minutes' exercise", "on days without")
    split("mindful", lambda d, _: None if d.get("mindful_minutes") is None and d.get("here_minutes") is None else (d.get("mindful_minutes") or 0) + (d.get("here_minutes") or 0) > 0,
          "on days you took mindful minutes", "on days you didn't")
    split("daylight", lambda d, _: None if d.get("daylight_minutes") is None else d["daylight_minutes"] >= 30, "on days with half an hour of daylight", "on days with less")

    # 9.2: what you drank, and training. Alcohol is the day before (it's the next day it shows), caffeine the same day.
    def drank(d: dict[str, Any], by: dict[str, Any]):
        prev = by.get((date.fromisoformat(d["date"]) - timedelta(days=1)).isoformat())
        if prev is None or prev.get("alcohol_drinks") is None and prev.get("logged_any") is None:
            return None
        return (prev.get("alcohol_drinks") or 0) >= 3

    split("alcohol", drank, "the day after 3 drinks or more", "after fewer")
    split("caffeine", lambda d, _: None if d.get("caffeine_mg") is None else d["caffeine_mg"] >= 300, "on days with 300 mg of caffeine or more", "on days with less")
    split("gym", lambda d, _: d.get("gym"), "on days you trained at the gym", "on days you didn't")
    return out


def overview(health_days: list[dict[str, Any]] | None, days: int = 30, gym_days: set[str] | None = None) -> dict[str, Any]:
    """The tab: each day's mood and mindful minutes, this week against last, patterns, the journal and the tools' time."""
    doc = load()
    here = Counter()
    for s in doc["sessions"]:
        here[s["at"][:10]] += s.get("seconds", 0) / 60
    rows = []
    for d in health_days or []:
        m = d.get("metrics") or {}
        v = valence(m)
        rows.append({"date": d.get("date"), "valence": v, "word": word(v), "entries": m.get("mood_entries"), "logged": m.get("mood"),
                     "mindful_minutes": m.get("mindful_minutes"), "here_minutes": round(here.get(d.get("date"), 0), 1) or None,
                     "sleep_hours": m.get("sleep_hours"), "exercise_minutes": m.get("exercise_minutes"), "daylight_minutes": m.get("daylight_minutes"),
                     "alcohol_drinks": m.get("alcohol_drinks"), "caffeine_mg": m.get("caffeine_mg"),
                     # a day with anything logged counts as no drinks when none were logged
                     "logged_any": 1 if any(k in m for k in ("water_ml", "caffeine_mg", "alcohol_drinks")) else None,
                     "gym": None if gym_days is None else d.get("date") in gym_days})
    t = today()
    week = [r for r in rows if r["date"] and r["date"] > (t - timedelta(days=7)).isoformat()]
    before = [r for r in rows if r["date"] and (t - timedelta(days=14)).isoformat() < r["date"] <= (t - timedelta(days=7)).isoformat()]

    def mindful(rs: list[dict[str, Any]]) -> float:
        return round(sum((r["mindful_minutes"] or 0) + (r["here_minutes"] or 0) for r in rs), 1)

    week_v = _avg([r["valence"] for r in week if r["valence"] is not None])
    before_v = _avg([r["valence"] for r in before if r["valence"] is not None])
    return {
        "available": health_days is not None,
        "days": rows[-days:],
        "today": next((r for r in rows if r["date"] == t.isoformat()), None),
        "week": {"valence": week_v, "word": word(week_v), "before": before_v, "mindful_minutes": mindful(week), "mindful_before": mindful(before),
                 "mood_days": sum(1 for r in week if r["valence"] is not None)},
        "patterns": patterns(rows),
        "journal_count": len(doc["journal"]),
        "tools_minutes_week": round(sum(s.get("seconds", 0) for s in doc["sessions"] if s["at"][:10] > (t - timedelta(days=7)).isoformat()) / 60, 1),
    }


def journal(limit: int = 30) -> list[dict[str, Any]]:
    """Newest first. Behind the lock (9.2)."""
    return sorted(load()["journal"], key=lambda j: j["at"], reverse=True)[:limit]


def add_journal(kind: str, text: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    doc = load()
    entry = {"id": _id(), "at": _now(), "kind": kind, "text": text.strip(), **(extra or {})}
    doc["journal"] = (doc["journal"] + [entry])[-MAX_JOURNAL:]
    save(doc)
    return entry


def delete_journal(entry_id: str) -> bool:
    doc = load()
    kept = [j for j in doc["journal"] if j["id"] != entry_id]
    if len(kept) == len(doc["journal"]):
        return False
    doc["journal"] = kept
    save(doc)
    return True


def add_session(tool: str, seconds: int) -> dict[str, Any]:
    doc = load()
    s = {"id": _id(), "at": _now(), "tool": tool, "seconds": seconds}
    doc["sessions"] = (doc["sessions"] + [s])[-MAX_SESSIONS:]
    save(doc)
    return s


# -- Clarity -------------------------------------------------------------------------------------------------------

def _streak(c: dict[str, Any], on: date) -> int:
    return max(0, (on - date.fromisoformat(c["start"])).days) if c.get("start") else 0


def clarity(on: date | None = None) -> dict[str, Any]:
    """The streak, your best, the last 30 days, urges this week and what sets them off, by time of day."""
    on = on or today()
    c = load()["clarity"]
    streak = _streak(c, on)
    best = max(c.get("best", 0), streak)
    last30 = [(on - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
    slips = {r["at"][:10] for r in c["resets"]}
    started = c.get("start")
    month = []
    for d in last30:
        status = c["checks"].get(d) or ("slip" if d in slips else ("clear" if started and d >= started and d < on.isoformat() else None))
        month.append({"date": d, "status": status})
    since = (on - timedelta(days=7)).isoformat()
    week_urges = [u for u in c["urges"] if u["at"][:10] > since]
    recent = [u for u in c["urges"] if u["at"][:10] > (on - timedelta(days=60)).isoformat()]
    triggers = Counter(u["trigger"] for u in recent if u.get("trigger"))
    times = Counter(_part(u["at"]) for u in recent)
    milestones = [7, 14, 30, 60, 90, 180, 365]
    nxt = next((m for m in milestones if m > streak), None)
    return {
        "started": started, "streak": streak, "best": best,
        "next": {"days": nxt, "left": nxt - streak} if nxt else None,
        "clear_last_30": sum(1 for m in month if m["status"] == "clear"), "month": month,
        "checked_today": c["checks"].get(on.isoformat()),
        "urges_week": len(week_urges), "rode_out_week": sum(1 for u in week_urges if u.get("outcome") == "rode"),
        "rode_out_all": sum(1 for u in c["urges"] if u.get("outcome") == "rode"),
        "triggers": [{"trigger": k, "count": n} for k, n in triggers.most_common(5)],
        "times": [{"part": p, "count": times.get(p, 0)} for p in ("morning", "afternoon", "evening", "late night")],
        "urges": sorted(c["urges"], key=lambda u: u["at"], reverse=True)[:10],
        "reasons": c["reasons"], "plan": c["plan"],
        "nudge": bool(c.get("nudge")), "risky": risky(c["urges"], on),
    }


def risky(urges: list[dict[str, Any]], on: date, need: int = 3) -> dict[str, Any] | None:
    """The hour urges come most (9.2), from the last 60 days, once there are at least `need` in it; the nudge goes half
    an hour before it."""
    since = (on - timedelta(days=60)).isoformat()
    hours = Counter()
    for u in urges:
        if u["at"][:10] > since:
            try:
                hours[datetime.fromisoformat(u["at"]).hour] += 1
            except ValueError:
                continue
    if not hours:
        return None
    hour, n = max(hours.items(), key=lambda kv: (kv[1], -kv[0]))
    if n < need:
        return None
    at = (datetime.combine(on, datetime.min.time()) + timedelta(hours=hour) - timedelta(minutes=30)).strftime("%H:%M")
    return {"hour": hour, "count": n, "nudge_at": at}


def set_nudge(on: bool) -> dict[str, Any]:
    doc = load()
    doc["clarity"]["nudge"] = on
    save(doc)
    return clarity()


def push_message(now: datetime) -> list[dict[str, Any]]:
    """The Clarity nudge (9.2), if you've turned it on: once a day, half an hour before the hour urges come most, worded
    so the lock screen gives nothing away."""
    from app.push.notifier import message

    c = load()["clarity"]
    if not c.get("nudge") or not c.get("start"):
        return []
    r = risky(c["urges"], now.date())
    if not r:
        return []
    h, m = (int(x) for x in r["nudge_at"].split(":"))
    fire = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if not fire <= now < fire + timedelta(minutes=30):
        return []
    return [message(f"mind:moment:{now.date().isoformat()}", "nudges", "A moment for you", "Check in with yourself.", url="/health?view=mind")]


def _part(at: str) -> str:
    try:
        h = datetime.fromisoformat(at).hour
    except ValueError:
        return "morning"
    return "morning" if 5 <= h < 12 else "afternoon" if h < 17 else "evening" if h < 22 else "late night"


def start(day: str | None = None) -> dict[str, Any]:
    doc = load()
    doc["clarity"]["start"] = day or today().isoformat()
    save(doc)
    return clarity()


def check(status: str, note: str = "") -> dict[str, Any]:
    """Today: clear, or a slip. A slip ends the streak (your best is kept) and it starts again from today."""
    doc = load()
    c = doc["clarity"]
    t = today()
    c["checks"][t.isoformat()] = status
    if status == "slip":
        c["best"] = max(c.get("best", 0), _streak(c, t))
        c["resets"].append({"at": _now(), "note": note[:300]})
        c["start"] = t.isoformat()
    elif not c.get("start"):
        c["start"] = t.isoformat()
    save(doc)
    return clarity()


def urge(trigger: str, outcome: str, note: str = "") -> dict[str, Any]:
    doc = load()
    c = doc["clarity"]
    c["urges"] = (c["urges"] + [{"id": _id(), "at": _now(), "trigger": trigger, "outcome": outcome, "note": note[:300]}])[-MAX_URGES:]
    save(doc)
    if outcome == "slip":
        return check("slip", note)
    return clarity()


def set_plan(reasons: list[str], plan: list[str]) -> dict[str, Any]:
    doc = load()
    doc["clarity"]["reasons"] = [r.strip() for r in reasons if r.strip()][:12]
    doc["clarity"]["plan"] = [p.strip() for p in plan if p.strip()][:12]
    save(doc)
    return clarity()


# -- habits (9.2) --------------------------------------------------------------------------------------------------

def _habit_stats(h: dict[str, Any], on: date) -> dict[str, Any]:
    done = set(h.get("done", []))
    streak, d = 0, on if on.isoformat() in done else on - timedelta(days=1)  # today not done yet doesn't break it
    while d.isoformat() in done:
        streak += 1
        d -= timedelta(days=1)
    best, run, prev = 0, 0, None
    for day in sorted(done):
        cur = date.fromisoformat(day)
        run = run + 1 if prev and (cur - prev).days == 1 else 1
        best, prev = max(best, run), cur
    month = [(on - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
    created = h.get("created", on.isoformat())
    span = [x for x in month if x >= created]
    return {"id": h["id"], "name": h["name"], "created": created, "streak": streak, "best": best, "today": on.isoformat() in done,
            "month": [{"date": x, "done": x in done} for x in month],
            "rate": round(100 * sum(1 for x in span if x in done) / len(span)) if span else 0}


def habits(on: date | None = None) -> list[dict[str, Any]]:
    on = on or today()
    return [_habit_stats(h, on) for h in load()["habits"] if not h.get("archived")]


def add_habit(name: str) -> list[dict[str, Any]]:
    doc = load()
    doc["habits"].append({"id": _id(), "name": name.strip(), "created": today().isoformat(), "done": []})
    doc["habits"] = doc["habits"][-50:]
    save(doc)
    return habits()


def _habit(doc: dict[str, Any], habit_id: str) -> dict[str, Any] | None:
    return next((h for h in doc["habits"] if h["id"] == habit_id and not h.get("archived")), None)


def mark_habit(habit_id: str, done: bool, day: str | None = None) -> list[dict[str, Any]] | None:
    doc = load()
    h = _habit(doc, habit_id)
    if h is None:
        return None
    d = day or today().isoformat()
    days = set(h.get("done", []))
    (days.add if done else days.discard)(d)
    h["done"] = sorted(days)[-1500:]
    save(doc)
    return habits()


def change_habit(habit_id: str, name: str | None = None, archived: bool | None = None) -> list[dict[str, Any]] | None:
    doc = load()
    h = _habit(doc, habit_id)
    if h is None:
        return None
    if name:
        h["name"] = name.strip()
    if archived:
        h["archived"] = True
    save(doc)
    return habits()
