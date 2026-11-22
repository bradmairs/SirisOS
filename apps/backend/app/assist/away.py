"""While you were away (11.3).

After 20 hours or more without SirisOS open on any device, the first screen is a short summary of what changed and
what's waiting, most important first:

1. what needs you (urgent and attention inbox items);
2. tasks overdue and due today;
3. money: a dip before pay, a charge that went up;
4. goals that slipped;
5. what's next in the calendar (the next day);
6. what came in the roundups meanwhile.

"Got it" marks everything in it as seen, so the notifications about those things don't come again.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.hub import sirisai_api
from app.hub.service import Hub
from app.services import json_store

AWAY_HOURS = 20


def _path():
    return json_store.data_path("SIRISOS_AWAY_PATH", "away.json")


def load() -> dict[str, Any]:
    return json_store.read(_path(), {}) or {}


def touch(now: datetime) -> None:
    doc = load()
    doc["last"] = now.isoformat(timespec="seconds")
    json_store.write(_path(), doc)


async def summary(hub: Hub, now: datetime) -> dict[str, Any]:
    doc = load()
    last = doc.get("last")
    if not last:
        touch(now)
        return {"away": False}
    since = datetime.fromisoformat(last)
    if now - since < timedelta(hours=AWAY_HOURS):
        return {"away": False, "since": last}
    items: list[dict[str, Any]] = []
    keys: list[str] = []
    try:
        from app.attention import service as attention

        inbox = [i for i in (await attention.inbox(hub))["items"] if i["severity"] in ("urgent", "attention")]
        if inbox:
            items.append({"kind": "inbox", "rank": 0 if any(i["severity"] == "urgent" for i in inbox) else 1,
                          "title": f"{len(inbox)} thing{'s' if len(inbox) != 1 else ''} need{'s' if len(inbox) == 1 else ''} you",
                          "lines": [i["title"] for i in inbox[:3]], "url": "/inbox"})
            keys += [f"inbox:{i['id']}" for i in inbox]
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.tasks import service as tasks

        col = await tasks.collect(hub, now.date())
        overdue, today = col["groups"].get("overdue", []), col["groups"].get("today", [])
        if overdue or today:
            bits = [f"{len(overdue)} overdue"] if overdue else []
            bits += [f"{len(today)} due today"] if today else []
            items.append({"kind": "tasks", "rank": 2, "title": "Tasks: " + ", ".join(bits), "lines": [t["title"] for t in (overdue + today)[:3]], "url": "/tasks"})
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.budget import forecast

        cf = forecast.cashflow(now.date())
        if cf.get("ready") and cf.get("warn"):
            items.append({"kind": "money", "rank": 3, "title": "Money's tight before pay",
                          "lines": [f"Down to about ${cf['low']['balance']:,.0f} on {datetime.fromisoformat(cf['low']['date']):%a %d %b}"], "url": "/budget"})
        ups = [r for r in forecast.recurring(now.date()) if "price_up" in r["flags"] and r.get("was") and r.get("status") not in ("ignore", "cancelling")]
        if ups:
            items.append({"kind": "money", "rank": 4, "title": "Charges that went up",
                          "lines": [f"{r['name']}: ${r['was']:,.2f} → ${r['amount']:,.2f}" for r in ups[:3]], "url": "/budget"})
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.assist import goals_steer

        behind = (await goals_steer.overview(hub, now.date()))["behind"]
        if behind:
            items.append({"kind": "goals", "rank": 5, "title": f"{len(behind)} goal{'s' if len(behind) != 1 else ''} behind",
                          "lines": [g["title"] + (f": {g['step']['text']}" if g.get("step") else "") for g in behind[:2]], "url": "/year"})
    except Exception:  # noqa: BLE001
        pass
    try:
        cal = await sirisai_api.get(hub, "/siris/hub/v1/calendar", params={"start": now.date().isoformat(), "end": (now.date() + timedelta(days=2)).isoformat()}, timeout=8.0) or {}
        soon = []
        for e in cal.get("events") or []:
            try:
                start = datetime.fromisoformat(str(e["start"]).replace("Z", "+00:00"))
                start = start if start.tzinfo else start.replace(tzinfo=now.tzinfo)
            except (KeyError, ValueError):
                continue
            if now <= start.astimezone(now.tzinfo) <= now + timedelta(hours=24):
                soon.append(f"{start.astimezone(now.tzinfo):%a %-I:%M%p}".replace("AM", "am").replace("PM", "pm") + f" {e.get('title') or 'Event'}")
        if soon:
            items.append({"kind": "calendar", "rank": 6, "title": "Next 24 hours", "lines": soon[:4], "url": "/"})
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.push import digest

        held = digest.load()["held"]
        if held:
            items.append({"kind": "roundup", "rank": 7, "title": f"{len(held)} waiting for the next roundup", "lines": [m["title"] for m in held[:4]], "url": "/inbox"})
            keys += [m["key"] for m in held]
    except Exception:  # noqa: BLE001
        pass
    items.sort(key=lambda i: i["rank"])
    hours = int((now - since).total_seconds() // 3600)
    return {"away": True, "since": last, "away_for": f"{hours // 24} day{'s' if hours // 24 != 1 else ''}" if hours >= 48 else f"{hours} hours",
            "items": items, "keys": keys}


def done(keys: list[str], now: datetime) -> None:
    """Got it: everything in the summary counts as seen, and the clock starts again."""
    from app.push import smart

    if keys:
        smart.mark_seen(keys, now)
    touch(now)
