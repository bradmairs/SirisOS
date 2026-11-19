"""The month in short (10.2): at the start of each month, last month on one card.

- **Money**: spent against the plan, lines over, and the change in net worth
  (from the bank imports and balances; left out until there are any).
- **Health**: sleep, resting heart rate, HRV, steps and exercise against the
  month before, and mood (Apple Health through SirisAI).
- **Work**: hours on the timesheet and CPD hours.
- **Habits**: how often each was kept on its days.

From the 1st (after 8am) it shows on Home until you've seen it, a notification
says it's ready, and it's filed in Siris as "<Month> recap" (tagged
monthly-recap). SirisGym's sessions aren't in it.

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


async def build(hub: Hub, ym: str, today: date) -> dict[str, Any]:
    return {"month": ym, "money": money(ym), "health": await health(hub, ym, today), "work": work(ym), "habits": habits(ym, today)}


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
