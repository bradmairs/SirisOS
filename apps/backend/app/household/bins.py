"""Bin night (10.4): which bins go out, the evening before collection.

Set each bin once: what it is (rubbish, recycling, green waste, glass) and one collection day it went out, and
how often (every week, fortnight or four weeks), as your council's calendar says. From 3pm the evening before,
Home says which bins; a notification at 7pm; on the morning, until 9am. Kept in bins.json (SIRISOS_BINS_PATH).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from app.services import json_store

KINDS = {"rubbish": "Rubbish", "recycling": "Recycling", "green": "Green waste", "glass": "Glass"}
PUSH_HOUR = 19


def _path():
    return json_store.data_path("SIRISOS_BINS_PATH", "bins.json")


def load() -> list[dict[str, Any]]:
    return list((json_store.read(_path(), {}) or {}).get("bins") or [])


def save(bins: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean = []
    for b in bins[:6]:
        if b.get("kind") not in KINDS:
            raise ValueError("A bin is rubbish, recycling, green or glass.")
        if int(b.get("every_weeks") or 0) not in (1, 2, 4):
            raise ValueError("Bins go out every 1, 2 or 4 weeks.")
        clean.append({"kind": b["kind"], "every_weeks": int(b["every_weeks"]), "first": date.fromisoformat(str(b["first"])[:10]).isoformat()})
    json_store.write(_path(), {"bins": clean})
    return clean


def on(day: date, bins: list[dict[str, Any]] | None = None) -> list[str]:
    """The bins collected on `day`."""
    out = []
    for b in bins if bins is not None else load():
        first = date.fromisoformat(b["first"])
        gap = (day - first).days
        if gap % (7 * b["every_weeks"]) == 0:
            out.append(b["kind"])
    return [k for k in KINDS if k in out]


def next_collection(today: date, bins: list[dict[str, Any]] | None = None) -> tuple[date, list[str]] | None:
    bins = bins if bins is not None else load()
    if not bins:
        return None
    for i in range(0, 29):
        d = today + timedelta(days=i)
        found = on(d, bins)
        if found:
            return d, found
    return None


def words(kinds: list[str]) -> str:
    names = [KINDS[k].lower() for k in kinds]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def card(local_now: datetime) -> dict[str, Any]:
    bins = load()
    nxt = next_collection(local_now.date(), bins)
    out: dict[str, Any] = {"bins": bins, "next": None, "show": False}
    if nxt:
        d, kinds = nxt
        out["next"] = {"date": d.isoformat(), "kinds": kinds, "text": words(kinds).capitalize()}
        eve = d - timedelta(days=1) == local_now.date() and local_now.hour >= 15
        morning = d == local_now.date() and local_now.hour < 9
        out["show"] = eve or morning
        out["when"] = "tonight" if eve else "this morning" if morning else None
    return out


def push_message(local_now: datetime) -> list[dict[str, Any]]:
    if local_now.hour < PUSH_HOUR:
        return []
    tomorrow = local_now.date() + timedelta(days=1)
    kinds = on(tomorrow)
    if not kinds:
        return []
    return [{"key": f"bins:{tomorrow.isoformat()}", "topic": "brief", "title": f"Bins out tonight: {words(kinds)}",
             "body": "Collection's tomorrow morning.", "url": "/", "urgency": "normal"}]
