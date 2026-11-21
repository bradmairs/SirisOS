"""Notification digest (10.2): the notifications that can wait come together,
in a morning and an evening roundup, instead of one at a time all day.

Straight away, as before:
- anything urgent (high urgency: an app down, an urgent inbox item);
- a task at its time;
- the Friday timesheet reminder and money getting tight before pay;
- bedtime and other time-of-day nudges;
- the weekly "notifications are working" check.

Everything else waits for the next roundup (07:30 and 18:00 by default). A
roundup with one thing in it is just that notification. Turn it off or change
the times in Notifications (settings). Kept in push-digest.json.

SirisAI's own alerts through ntfy aren't SirisOS's to hold: only what SirisOS
sends (which includes SirisAI's inbox) comes together here.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.services import json_store

DEFAULT_TIMES = ["07:30", "18:00"]
NOW_PREFIXES = ("task:", "timesheet:", "cashflow:", "nudge:", "push-check:", "digest:", "travel:", "fuel:", "bins:", "bedroom:")
MAX_HELD = 60
_TIME = re.compile(r"([01]\d|2[0-3]):[0-5]\d")


def _path():
    return json_store.data_path("SIRISOS_DIGEST_PATH", "push-digest.json")


def load() -> dict[str, Any]:
    doc = json_store.read(_path(), {}) or {}
    doc.setdefault("on", True)
    doc.setdefault("times", list(DEFAULT_TIMES))
    doc.setdefault("held", [])
    doc.setdefault("last", None)
    return doc


def save(doc: dict[str, Any]) -> None:
    doc["held"] = doc["held"][-MAX_HELD:]
    json_store.write(_path(), doc)


def settings() -> dict[str, Any]:
    doc = load()
    return {"on": doc["on"], "times": doc["times"], "waiting": len(doc["held"]),
            "titles": [m["title"] for m in doc["held"]][-10:]}


def change(on: bool | None = None, times: list[str] | None = None) -> dict[str, Any]:
    doc = load()
    if on is not None:
        doc["on"] = on
    if times is not None:
        good = sorted({t for t in times if _TIME.fullmatch(t)})
        if not good:
            raise ValueError("Give at least one time, like 07:30.")
        doc["times"] = good[:4]
    save(doc)
    return settings()


def straight_away(msg: dict[str, Any]) -> bool:
    return msg.get("urgency") == "high" or str(msg.get("key", "")).startswith(NOW_PREFIXES)


def split(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(send now, hold for the roundup). With the digest off, everything goes now."""
    if not load()["on"]:
        return messages, []
    now = [m for m in messages if straight_away(m)]
    return now, [m for m in messages if not straight_away(m)]


def hold(messages: list[dict[str, Any]], local_now: datetime) -> None:
    if not messages:
        return
    doc = load()
    have = {m["key"] for m in doc["held"]}
    at = local_now.strftime("%Y-%m-%d %H:%M")
    doc["held"] += [{k: m.get(k) for k in ("key", "topic", "title", "body", "url")} | {"at": at} for m in messages if m["key"] not in have]
    save(doc)


def _slot(local_now: datetime, times: list[str]) -> str | None:
    """The latest roundup time today that has passed, as 'YYYY-MM-DD HH:MM'."""
    passed = [t for t in times if local_now.strftime("%H:%M") >= t]
    return f"{local_now.date().isoformat()} {passed[-1]}" if passed else None


def slot_due(local_now: datetime) -> bool:
    doc = load()
    slot = _slot(local_now, doc["times"])
    return bool(slot and not (doc["last"] and doc["last"] >= slot) and doc["held"])


def replace_held(held: list[dict[str, Any]]) -> None:
    doc = load()
    doc["held"] = held
    save(doc)


def due(local_now: datetime) -> dict[str, Any] | None:
    """The roundup to send now, if a roundup time has passed since the last one and something's waiting; it's then cleared."""
    doc = load()
    slot = _slot(local_now, doc["times"])
    if not slot or (doc["last"] and doc["last"] >= slot):
        return None
    # Only what was waiting before this roundup's time: something held at 10am waits for the evening, not the 7:30 one.
    held = [m for m in doc["held"] if (m.get("at") or "") <= slot]
    doc["last"] = slot
    doc["held"] = [m for m in doc["held"] if (m.get("at") or "") > slot]
    save(doc)
    if not held:
        return None
    if len(held) == 1:
        m = held[0]
        return {**m, "key": f"digest:{slot}", "urgency": "normal", "target": None, "actions": []}
    morning = slot[11:] < "12:00"
    lines = [f"• {m['title']}" for m in held[:6]]
    if len(held) > 6:
        lines.append(f"and {len(held) - 6} more")
    topics = {m.get("topic") for m in held}
    return {"key": f"digest:{slot}", "topic": topics.pop() if len(topics) == 1 else "brief",
            "title": f"{'Morning' if morning else 'Evening'} roundup: {len(held)} things", "body": "\n".join(lines),
            "url": "/inbox", "urgency": "normal", "target": None, "actions": [], "topics": sorted(t for t in {m.get("topic") for m in held} if t)}
