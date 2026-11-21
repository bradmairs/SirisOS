"""The weekend planner (10.4): on Thursday, the best windows on Saturday and Sunday for a run, hike, ride or
walk, from the hourly forecast, your free time in the calendar and your readiness, each with one of your routes.

- **A good hour**: in daylight (sunrise to sunset), dry (rain chance under 30%, under 0.3 mm), not too cold or
  hot (8 to 27°C), not too windy (under 35 km/h), and nothing in the calendar.
- **A window**: a run of good hours, at least an hour long (four at most). Mornings and about 18°C score best.
- **A route**: one of yours (Fitness: your routes) that fits the window; an easy one (or a walk) when your
  readiness says to recover.

Shown on Home from Thursday to Sunday, with one notification on Thursday at 5pm (in the evening roundup). Kept in weekend.json
(SIRISOS_WEEKEND_PATH): your routes.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any

from app.hub.service import Hub
from app.outdoors import weather
from app.services import json_store

KINDS = ("run", "hike", "ride", "walk", "other")
GOOD = {"rain_chance": 30, "rain_mm": 0.3, "min_c": 8, "max_c": 27, "wind_kmh": 35}
PUSH_HOUR = 17  # rides the 6pm roundup


def _path():
    return json_store.data_path("SIRISOS_WEEKEND_PATH", "weekend.json")


def load() -> dict[str, Any]:
    doc = json_store.read(_path(), {}) or {}
    doc.setdefault("routes", [])
    return doc


def set_routes(routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean = []
    for r in routes[:40]:
        name = str(r.get("name") or "").strip()[:80]
        if not name:
            continue
        hours = max(0.25, min(12.0, float(r.get("hours") or 1)))
        clean.append({"id": str(r.get("id") or uuid.uuid4().hex[:10])[:20], "name": name,
                      "kind": r.get("kind") if r.get("kind") in KINDS else "other", "hours": round(hours, 2),
                      "km": round(float(r["km"]), 1) if r.get("km") not in (None, "") else None,
                      "link": str(r.get("link") or "").strip()[:300] or None, "notes": str(r.get("notes") or "").strip()[:200]})
    doc = load()
    doc["routes"] = clean
    json_store.write(_path(), doc)
    return clean


def weekend_days(today: date) -> list[date]:
    """This coming Saturday and Sunday (or what's left of the weekend)."""
    if today.weekday() == 6:
        return [today]
    sat = today + timedelta(days=(5 - today.weekday()) % 7)
    return [sat, sat + timedelta(days=1)]


def _busy(events: list[dict[str, Any]] | None) -> list[tuple[str, str]]:
    out = []
    for e in events or []:
        start, end = str(e.get("start") or ""), str(e.get("end") or "")
        if len(start) > 10 and len(end) > 10:  # timed events only; all-day ones don't block the morning
            out.append((start[:16], end[:16]))
    return out


def good_hour(h: dict[str, Any]) -> bool:
    t = h.get("temperature_c")
    return (t is not None and GOOD["min_c"] <= t <= GOOD["max_c"] and (h.get("rain_chance_percent") or 0) < GOOD["rain_chance"]
            and (h.get("rain_mm") or 0) < GOOD["rain_mm"] and (h.get("wind_kmh") or 0) < GOOD["wind_kmh"])


def windows(hours: list[dict[str, Any]], sun: list[dict[str, Any]], days: list[date], busy: list[tuple[str, str]]) -> list[dict[str, Any]]:
    light = {s["date"]: (str(s.get("sunrise") or "")[11:16], str(s.get("sunset") or "")[11:16]) for s in sun}
    out = []
    for d in days:
        rise, set_ = light.get(d.isoformat(), ("06:00", "20:00"))
        todays = [h for h in hours if h["time"][:10] == d.isoformat() and rise <= h["time"][11:16] and h["time"][11:16] < set_]
        run: list[dict[str, Any]] = []

        def close(run: list[dict[str, Any]]) -> None:
            if len(run) < 1:
                return
            for i in range(0, len(run), 4):  # long good stretches are split into up-to-4-hour windows
                part = run[i:i + 4]
                if len(part) < 1:
                    continue
                temps = [h["temperature_c"] for h in part]
                start = part[0]["time"]
                end_dt = datetime.fromisoformat(part[-1]["time"]) + timedelta(hours=1)
                morning = 6 <= int(start[11:13]) <= 10
                score = 100 - sum(abs(t - 18) for t in temps) / len(temps) * 3 - max(h.get("rain_chance_percent") or 0 for h in part) * 0.5 \
                    - max(h.get("wind_kmh") or 0 for h in part) * 0.4 + (10 if morning else 0) + len(part) * 2
                out.append({"date": d.isoformat(), "start": start[11:16], "end": end_dt.strftime("%H:%M"), "hours": len(part),
                            "low_c": round(min(temps)), "high_c": round(max(temps)), "rain_chance": max(h.get("rain_chance_percent") or 0 for h in part),
                            "conditions": part[len(part) // 2].get("conditions"), "score": round(score, 1)})

        for h in todays:
            t = h["time"][:16]
            t_end = (datetime.fromisoformat(t) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
            if good_hour(h) and not any(s < t_end and e > t for s, e in busy):  # the hour overlaps nothing in the calendar
                run.append(h)
            else:
                close(run)
                run = []
        close(run)
    return out


def pick_route(routes: list[dict[str, Any]], hours: float, recover: bool) -> dict[str, Any] | None:
    fits = [r for r in routes if r["hours"] <= hours]
    if not fits:
        return None
    if recover:
        easy = [r for r in fits if r["kind"] == "walk"] or fits
        return min(easy, key=lambda r: r["hours"])
    return max(fits, key=lambda r: r["hours"])


async def plan(hub: Hub, today: date) -> dict[str, Any]:
    from app.calendar import service as calendar
    from app.hub import sirisai_api

    days = weekend_days(today)
    doc = load()
    wx = await weather.hourly(hub, days=min(7, (days[-1] - today).days + 1))
    if wx is None:
        return {"days": [d.isoformat() for d in days], "windows": [], "routes": doc["routes"], "readiness": None,
                "note": "The forecast isn't available from SirisAI right now."}
    cal = await calendar.events(hub, days[0], days[-1] + timedelta(days=1))
    overview = await sirisai_api.get(hub, "/siris/hub/v1/health/overview", timeout=15.0) or {}
    readiness = overview.get("readiness") or None
    recover = bool(readiness and readiness.get("band") == "Recover")
    found = windows(wx["hours"], wx.get("sun") or [], days, _busy(cal.get("events")))
    best = sorted(found, key=lambda w: -w["score"])[:3]
    for w in best:
        w["route"] = pick_route(doc["routes"], w["hours"], recover)
    best.sort(key=lambda w: (w["date"], w["start"]))
    note = None
    if not found:
        note = "No good window this weekend: wet, windy, too hot or cold, or the calendar's full."
    elif not doc["routes"]:
        note = "Add your routes (a loop, a trail, a ride) and each window gets one that fits."
    return {"days": [d.isoformat() for d in days], "windows": best, "routes": doc["routes"],
            "readiness": {"score": readiness.get("score"), "band": readiness.get("band")} if readiness else None, "recover": recover, "note": note}


def describe(w: dict[str, Any]) -> str:
    d = date.fromisoformat(w["date"])
    def hm(t: str) -> str:
        h, m = int(t[:2]), int(t[3:])
        return f"{h % 12 or 12}{':%02d' % m if m else ''}{'am' if h < 12 else 'pm'}"
    route = f": {w['route']['name']} ({w['route']['hours']:g} h)" if w.get("route") else ""
    return f"{d:%a} {hm(w['start'])}–{hm(w['end'])}, {(w.get('conditions') or 'fine').lower()}, {w['low_c']}–{w['high_c']}°{route}"


async def push_message(hub: Hub, local_now: datetime) -> list[dict[str, Any]]:
    """Thursday, 5 to 6pm (once): the work's only done in that hour, and not again once sent."""
    from app.push import store

    if local_now.weekday() != 3 or local_now.hour != PUSH_HOUR:
        return []
    if f"weekend:{weekend_days(local_now.date())[0].isoformat()}" in store.sent():
        return []
    p = await plan(hub, local_now.date())
    if not p["windows"]:
        return []
    more = len(p["windows"]) - 1
    return [{"key": f"weekend:{p['days'][0]}", "topic": "brief", "title": "Your weekend outside",
             "body": f"Best: {describe(max(p['windows'], key=lambda w: w['score']))}." + (f" {more} more window{'s' * (more != 1)} on Home." if more else ""),
             "url": "/", "urgency": "normal"}]
