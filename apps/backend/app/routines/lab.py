"""Home Lab additions (10.4): container updates and the internet's speed, from SirisAI 7.3.

- **Container updates**: SirisAI checks the Docker host every morning (5am) for newer images. Home Lab lists
  them, with release notes when there are some; "Update" does one, "Update all" the lot. SirisAI pulls the new
  image, starts it, checks it comes up healthy, and puts the old one back if it doesn't.
- **Internet speed**: SirisAI's speed tests (every 6 hours) and drops, charted against your NBN plan's speed (set
  here). When three days in a row average under half the plan, one notification says so: the history is the
  evidence for your provider. Kept in lab.json (SIRISOS_LAB_PATH): the plan's speeds.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import median
from typing import Any

from app.brief.service import zone
from app.hub import sirisai_api
from app.hub.service import Hub
from app.services import json_store

SLOW_DAYS = 3
SLOW_SHARE = 0.5


def _path():
    return json_store.data_path("SIRISOS_LAB_PATH", "lab.json")


def plan() -> dict[str, Any]:
    doc = json_store.read(_path(), {}) or {}
    return {"down": doc.get("plan_down"), "up": doc.get("plan_up")}


def set_plan(down: float | None, up: float | None) -> dict[str, Any]:
    doc = json_store.read(_path(), {}) or {}
    doc["plan_down"], doc["plan_up"] = down, up
    json_store.write(_path(), doc)
    return plan()


def daily(speeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each local day's median download and upload."""
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in speeds:
        if s.get("down") is None:
            continue
        day = datetime.fromisoformat(s["at"]).astimezone(zone()).date().isoformat()
        by[day].append(s)
    return [{"date": d, "down": round(median(x["down"] for x in v), 1),
             "up": round(median(x["up"] for x in v if x.get("up") is not None), 1) if any(x.get("up") is not None for x in v) else None,
             "tests": len(v)} for d, v in sorted(by.items())]


def slow_streak(days: list[dict[str, Any]], plan_down: float | None) -> list[dict[str, Any]]:
    if not plan_down or len(days) < SLOW_DAYS:
        return []
    last = days[-SLOW_DAYS:]
    return last if all(d["down"] < plan_down * SLOW_SHARE for d in last) else []


async def internet(hub: Hub, days: int = 30) -> dict[str, Any]:
    body = await sirisai_api.get(hub, "/siris/hub/v1/internet", params={"days": days}, timeout=15.0)
    if not isinstance(body, dict) or not body.get("available", True):
        return {"available": False, "plan": plan()}
    d = daily(body.get("speeds") or [])
    p = plan()
    return {**body, "daily": d, "plan": p, "slow": slow_streak(d, p["down"]),
            "share_of_plan": round(100 * median(x["down"] for x in d) / p["down"]) if d and p["down"] else None}


async def push_message(hub: Hub, local_now: datetime) -> list[dict[str, Any]]:
    """Once a day at 9am: three slow days in a row (against the plan)."""
    from app.push import store

    if local_now.hour != 9 or not plan()["down"] or f"internet-slow:{local_now.date().isoformat()}" in store.sent():
        return []
    i = await internet(hub, 7)
    slow = i.get("slow") or []
    if not slow:
        return []
    avg = round(sum(d["down"] for d in slow) / len(slow))
    return [{"key": f"internet-slow:{local_now.date().isoformat()}", "topic": "apps", "title": "The internet's been slow",
             "body": f"About {avg} Mbps for {len(slow)} days on a {i['plan']['down']:g} Mbps plan. The speed history is in Home Lab if you contact your provider.",
             "url": "/homelab", "urgency": "normal"}]
