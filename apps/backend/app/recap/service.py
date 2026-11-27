"""The month in short (10.2): at the start of each month, last month on one card.

- **Money**: spent against the plan, lines over, and the change in net worth
  (from the bank imports and balances; left out until there are any).
- **Health**: sleep, resting heart rate, HRV, steps and exercise against the
  month before, and mood (Apple Health through SirisAI).
- **Work**: hours on the timesheet and CPD hours.
- **Habits**: how often each was kept on its days.
- **The gym** (11.15): workouts, volume and new records, against the month before.
- **Goals** (11.15): the year's goals behind the pace.
- **Where you went** (11.15): the sections opened most, and ones not opened at all (from 11.10's visit counts).
- **Coming up** (11.15): renewals due in the next 30 days.

From the 1st (after 8am) it shows on Home until you've seen it, a notification
says it's ready, and it's filed in Siris as "<Month> recap" (tagged
monthly-recap).

Kept in recap.json (SIRISOS_RECAP_PATH): which months were filed and seen.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Any

from app.hub import sirisai_api
from app.hub.service import Hub
from app.services import json_store

RECAP_HOUR = 8
SHOW_DAYS = 7


def _path():
    return json_store.data_path("SIRISOS_RECAP_PATH", "recap.json")


def _state() -> dict[str, Any]:
    return json_store.read(_path(), {}) or {}


def _save(state: dict[str, Any]) -> None:
    json_store.write(_path(), dict(sorted(state.items())[-24:]))


def last_month(today: date) -> str:
    first = today.replace(day=1)
    return (first - timedelta(days=1)).strftime("%Y-%m")


def _prev(ym: str) -> str:
    return (date.fromisoformat(f"{ym}-01") - timedelta(days=1)).strftime("%Y-%m")


def _bounds(ym: str) -> tuple[date, date]:
    y, m = int(ym[:4]), int(ym[5:])
    return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])


def money(ym: str) -> dict[str, Any] | None:
    from app.budget import actuals
    from app.budget import service as budget

    m = actuals.month(ym)
    bal = actuals.balances()
    by = {s["month"]: s["net_worth"] for s in bal["series"]}
    if not m["has_data"] and ym not in by:
        return None
    plan = budget.get()
    planned = sum(budget.monthly(l) for s in ("expenses", "spending") for l in plan.get("sections", {}).get(s, []))
    nw, before = by.get(ym), by.get(_prev(ym))
    return {"spent": m["spent"] if m["has_data"] else None, "planned": round(planned, 2), "over": [o["name"] for o in m["over"]],
            "net_worth": nw, "net_worth_change": round(nw - before, 2) if nw is not None and before is not None else None,
            "currency": m["currency"]}


async def health(hub: Hub, ym: str, today: date) -> dict[str, Any] | None:
    start, _ = _bounds(_prev(ym))
    body = await sirisai_api.get(hub, "/siris/hub/v1/health/days", params={"days": min(400, (today - start).days + 1)}, timeout=15.0)
    days = (body or {}).get("days") or []
    if not days:
        return None
    from app.mind import service as mind

    def avg(month: str, key: str) -> float | None:
        if key == "mood":
            vals = [v for d in days if str(d.get("date", "")).startswith(month) and (v := mind.valence(d.get("metrics") or {})) is not None]
        else:
            vals = [d["metrics"][key] for d in days if str(d.get("date", "")).startswith(month) and (d.get("metrics") or {}).get(key) is not None]
        return round(mean(vals), 2) if vals else None

    out = {}
    for key in ("sleep_hours", "resting_heart_rate", "heart_rate_variability", "steps", "exercise_minutes", "mood"):
        now_, then = avg(ym, key), avg(_prev(ym), key)
        if now_ is not None:
            out[key] = {"value": now_, "before": then}
    if "mood" in out:
        out["mood"]["word"] = mind.word(out["mood"]["value"])
    return out or None


def work(ym: str) -> dict[str, Any]:
    from app.career import store as career_store
    from app.work import timesheet

    hours = round(sum(e["hours"] for e in timesheet.load() if e["date"].startswith(ym)), 1)
    cpd = round(sum(r.hours for r in career_store.load().cpd.records if r.date and r.date.startswith(ym)), 1)
    return {"timesheet_hours": hours, "cpd_hours": cpd}


def habits(ym: str, today: date) -> list[dict[str, Any]]:
    from app.mind import service as mind

    start, end = _bounds(ym)
    end = min(end, today)
    out = []
    for h in mind.load()["habits"]:
        if h.get("archived"):
            continue
        since = max(start, date.fromisoformat(h.get("created") or start.isoformat()))
        due = [since + timedelta(days=i) for i in range((end - since).days + 1)]
        due = [d for d in due if mind._due(h, d)]  # noqa: SLF001
        if not due:
            continue
        done = set(h.get("done", []))
        kept = sum(1 for d in due if d.isoformat() in done)
        out.append({"name": h["name"], "kept": kept, "of": len(due), "rate": round(kept / len(due), 2)})
    return out


def gym(ym: str) -> dict[str, Any] | None:
    """11.15: the month's workouts, volume and new records, and last month's count to compare."""
    from app.gym import service as gs, store as gym_store

    try:
        doc = gym_store.load()
    except Exception:  # noqa: BLE001
        return None
    month = [s for s in gym_store.counted(doc) if gs.day_of(s.started_at).startswith(ym)]
    before = sum(1 for s in gym_store.counted(doc) if gs.day_of(s.started_at).startswith(_prev(ym)))
    if not month and not before:
        return None
    records = [r["text"] for s in month for r in gs.new_records(doc, s)]
    return {"workouts": len(month), "before": before, "volume": round(sum(gs.summary(doc, s)["volume"] for s in month)),
            "records": len(records), "top_records": records[:3]}


async def goals(hub: Hub, today: date) -> list[dict[str, Any]] | None:
    """11.15: this year's goals behind the pace for the time of year."""
    try:
        from app.goals import service as gl

        g = await gl.overview(hub, today.year, today)
    except Exception:  # noqa: BLE001
        return None
    return [{"title": x["title"], "percent": x["percent"], "through": g["through_year"]} for x in g["goals"] if x["state"] == "behind"][:4] or None


def places(ym: str) -> dict[str, Any] | None:
    """11.15: the sections opened most last month, and ones never opened (when the counting covers the month)."""
    from app.assist import homeuse

    visits = homeuse.load().get("visits") or {}
    days: dict[str, set[str]] = {}
    for by_path in visits.values():
        for path, when in by_path.items():
            days.setdefault(path, set()).update(d for d in when if d.startswith(ym))
    opened = {p: len(d) for p, d in days.items() if d}
    if not opened:
        return None
    first = min(d for by_path in visits.values() for when in by_path.values() for d in when)
    top = sorted(opened.items(), key=lambda kv: -kv[1])[:3]
    return {"top": [{"path": p, "days": n} for p, n in top], "counting_since": first}


def ahead(today: date) -> list[dict[str, Any]]:
    """11.15: renewals due in the 30 days from `today` (the recap comes at the start of a month)."""
    from app.renewals import service as renewals

    return [{"name": r["name"], "expires": r["expires"]} for r in renewals.listing(today) if 0 <= r["days_left"] <= 30][:5]


async def build(hub: Hub, ym: str, today: date) -> dict[str, Any]:
    return {"month": ym, "money": money(ym), "health": await health(hub, ym, today), "work": work(ym), "habits": habits(ym, today),
            "gym": gym(ym), "goals": await goals(hub, today), "places": places(ym), "ahead": ahead(today)}


def _money_str(v: float, cur: str) -> str:
    from app.budget import service as budget

    return budget._money(v, cur)  # noqa: SLF001


def as_text(r: dict[str, Any]) -> str:
    """The recap in plain lines, for Siris and the notification."""
    lines = []
    m = r.get("money")
    if m:
        if m["spent"] is not None:
            lines.append(f"Spent {_money_str(m['spent'], m['currency'])} against {_money_str(m['planned'], m['currency'])} planned"
                         + (f"; over on {', '.join(m['over'])}" if m["over"] else "") + ".")
        if m["net_worth_change"] is not None:
            lines.append(f"Net worth {'up' if m['net_worth_change'] >= 0 else 'down'} {_money_str(abs(m['net_worth_change']), m['currency'])}"
                         f" to {_money_str(m['net_worth'], m['currency'])}.")
    h = r.get("health") or {}
    if "sleep_hours" in h:
        lines.append(f"Slept {h['sleep_hours']['value']:.1f} h a night" + (f" (from {h['sleep_hours']['before']:.1f})" if h["sleep_hours"]["before"] else "") + ".")
    if "resting_heart_rate" in h:
        lines.append(f"Resting heart rate {h['resting_heart_rate']['value']:.0f} bpm" + (f" (from {h['resting_heart_rate']['before']:.0f})" if h["resting_heart_rate"]["before"] else "") + ".")
    if "heart_rate_variability" in h:
        lines.append(f"HRV {h['heart_rate_variability']['value']:.0f} ms" + (f" (from {h['heart_rate_variability']['before']:.0f})" if h["heart_rate_variability"]["before"] else "") + ".")
    if "steps" in h:
        lines.append(f"{h['steps']['value']:,.0f} steps a day" + (f" (from {h['steps']['before']:,.0f})" if h["steps"]["before"] else "") + ".")
    if "mood" in h:
        lines.append(f"Mood mostly {str(h['mood']['word']).lower()}.")
    w = r.get("work") or {}
    if w.get("timesheet_hours"):
        lines.append(f"{w['timesheet_hours']:g} h on the timesheet.")
    if w.get("cpd_hours"):
        lines.append(f"{w['cpd_hours']:g} h of CPD.")
    for hb in r.get("habits") or []:
        lines.append(f"{hb['name']}: {hb['kept']} of {hb['of']} days.")
    g = r.get("gym")
    if g:
        lines.append(f"{g['workouts']} workout{'' if g['workouts'] == 1 else 's'}" + (f" (from {g['before']})" if g["before"] != g["workouts"] else "")
                     + f", {g['volume']:,} kg lifted" + (f", {g['records']} new best{'' if g['records'] == 1 else 's'}: {'; '.join(g['top_records'])}" if g["records"] else "") + ".")
    for goal in r.get("goals") or []:
        lines.append(f"Behind on {goal['title']}: {goal['percent'] or 0}% there, {goal['through']}% through the year.")
    p = r.get("places")
    if p:
        lines.append("Opened most: " + ", ".join(f"{x['path'].strip('/').title() or 'Home'} ({x['days']} days)" for x in p["top"]) + ".")
    for a in r.get("ahead") or []:
        lines.append(f"Renewing soon: {a['name']} ({date.fromisoformat(a['expires'][:10]):%-d %b}).")
    return "\n".join(f"- {line}" for line in lines) or "- A quiet month: nothing recorded."


def title(ym: str) -> str:
    return f"{date.fromisoformat(ym + '-01'):%B %Y} recap"


async def view(hub: Hub, today: date, ym: str | None = None) -> dict[str, Any]:
    ym = ym or last_month(today)
    r = await build(hub, ym, today)
    st = _state().get(ym, {})
    return {**r, "title": title(ym), "text": as_text(r), "filed_as": st.get("filed_as"), "seen": bool(st.get("seen")),
            "show": ym == last_month(today) and today.day <= SHOW_DAYS and not st.get("seen")}


def seen(ym: str) -> None:
    state = _state()
    state.setdefault(ym, {})["seen"] = True
    _save(state)


async def push_message(hub: Hub, local_now: datetime) -> list[dict[str, Any]]:
    """On the 1st (from 8am) or soon after: file last month's recap in Siris, once, and say it's ready."""
    today = local_now.date()
    if today.day > SHOW_DAYS or (today.day == 1 and local_now.hour < RECAP_HOUR):
        return []
    ym = last_month(today)
    state = _state()
    if state.get(ym, {}).get("filed_at"):
        return []
    r = await build(hub, ym, today)
    text = as_text(r)
    filed = None
    try:
        res = await sirisai_api.post(hub, "/siris/brain/capture", json={"title": title(ym), "text": text, "tags": ["monthly-recap"]}, timeout=30.0)
        filed = (res or {}).get("title") or title(ym)
    except sirisai_api.SirisAIError:
        return []  # SirisAI's away: try again next time
    state.setdefault(ym, {}).update({"filed_as": filed, "filed_at": local_now.isoformat(timespec="minutes")})
    _save(state)
    first = text.splitlines()[0][2:] if text else ""
    return [{"key": f"recap:{ym}", "topic": "brief", "title": f"Your {date.fromisoformat(ym + '-01'):%B} in short",
             "body": first + " See it on Home.", "url": "/", "urgency": "normal"}]
