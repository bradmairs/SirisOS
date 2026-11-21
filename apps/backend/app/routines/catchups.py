"""Catch-ups (10.4): the people you keep in touch with (Things & People: "keep in touch every..."), when it's been
longer than that, with the free parts of the coming weekend. "Caught up" logs it (last contact: today). On Home
when someone's overdue, and a nudge on Friday at noon when there's someone and a free weekend afternoon.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from app.hub import sirisai_api
from app.hub.service import Hub

PARTS = (("morning", 9, 12), ("afternoon", 12, 17), ("evening", 17, 21))


def overdue(people: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    out = []
    for p in people:
        gap = p.get("keep_in_touch_days")
        if not gap:
            continue
        last = p.get("last_contact")
        since = (today - date.fromisoformat(str(last)[:10])).days if last else None
        if since is None or since > gap:
            out.append({"id": p["id"], "name": p["name"], "relation": p.get("relation"), "days_since": since, "gap": gap,
                        "over_by": (since - gap) if since is not None else None})
    return sorted(out, key=lambda x: -(x["over_by"] if x["over_by"] is not None else 10_000))


def free_parts(events: list[dict[str, Any]] | None, days: list[date]) -> list[dict[str, Any]]:
    out = []
    for d in days:
        for part, start, end in PARTS:
            a, b = f"{d.isoformat()}T{start:02d}:00", f"{d.isoformat()}T{end:02d}:00"
            if not any(len(str(e.get("start") or "")) > 10 and str(e["start"])[:16] < b and str(e.get("end") or "")[:16] > a for e in events or []):
                out.append({"date": d.isoformat(), "part": part})
    return out


async def overview(hub: Hub, today: date) -> dict[str, Any]:
    from app.calendar import service as calendar
    from app.outdoors.weekend import weekend_days

    people = await sirisai_api.get(hub, "/siris/people", timeout=15.0)
    if not isinstance(people, list):
        return {"available": False, "overdue": [], "free": []}
    days = weekend_days(today)
    cal = await calendar.events(hub, days[0], days[-1] + timedelta(days=1))
    return {"available": True, "overdue": overdue(people, today), "free": free_parts(cal.get("events"), days),
            "keeping_up": sum(1 for p in people if p.get("keep_in_touch_days"))}


async def caught_up(hub: Hub, person_id: int, on: date) -> Any:
    r = await sirisai_api.raw(hub, "PUT", f"/siris/people/{person_id}", json={"last_contact": on.isoformat()}, timeout=15.0)
    if r.status_code >= 400:
        raise sirisai_api.SirisAIError("SirisAI didn't take it.", 404 if r.status_code == 404 else 502)
    return r.json()


async def set_gap(hub: Hub, person_id: int, days: int | None) -> Any:
    r = await sirisai_api.raw(hub, "PUT", f"/siris/people/{person_id}", json={"keep_in_touch_days": days}, timeout=15.0)
    if r.status_code >= 400:
        raise sirisai_api.SirisAIError("SirisAI didn't take it.", 404 if r.status_code == 404 else 502)
    return r.json()


async def push_message(hub: Hub, local_now: datetime) -> list[dict[str, Any]]:
    from app.push import store

    if local_now.weekday() != 4 or local_now.hour != 12 or f"catchup:{local_now.date().isoformat()}" in store.sent():
        return []
    o = await overview(hub, local_now.date())
    afternoons = [f for f in o["free"] if f["part"] == "afternoon"]
    if not o["overdue"] or not afternoons:
        return []
    who = o["overdue"][0]
    when = date.fromisoformat(afternoons[0]["date"])
    since = f"{who['days_since']} days" if who["days_since"] is not None else "a while"
    return [{"key": f"catchup:{local_now.date().isoformat()}", "topic": "brief", "title": f"Catch up with {who['name']}?",
             "body": f"It's been {since}. {when:%A} afternoon's free.", "url": "/", "urgency": "normal"}]
