"""Home that learns what you use (11.3).

Home tells SirisOS, per part of the day, which cards were shown (once a day each) and which you tapped. Over the last
four weeks:

- cards you tap rise within their section, more taps per day shown, higher;
- a card with something to tap (a button or a link) that's been shown on 10 or more days without one tap is tucked
  under "Show everything" for that part of the day. Cards there just to read (the weather) are never tucked;
- one tap on a tucked card (from Show everything) brings it straight back.

Turn it off on Customise Home. Kept in home-usage.json.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.services import json_store

KEEP_DAYS = 28
TUCK_AFTER_DAYS = 10
PHASES = ("morning", "work", "weekend", "evening", "winddown", "night")


def _path():
    return json_store.data_path("SIRISOS_HOME_USAGE_PATH", "home-usage.json")


def load() -> dict[str, Any]:
    doc = json_store.read(_path(), {}) or {}
    doc.setdefault("on", True)
    doc.setdefault("phases", {})
    return doc


def record(events: list[dict[str, Any]], today: date) -> None:
    doc = load()
    day = today.isoformat()
    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
    for e in events[:200]:
        phase, widget, kind = e.get("phase"), str(e.get("widget") or "")[:80], e.get("kind")
        if phase not in PHASES or not widget or kind not in ("seen", "tap"):
            continue
        w = doc["phases"].setdefault(phase, {}).setdefault(widget, {"days": {}, "interactive": False})
        counts = w["days"].setdefault(day, [0, 0])
        if kind == "seen":
            counts[0] = 1
            w["interactive"] = bool(e.get("interactive")) or w["interactive"]
        else:
            counts[0], counts[1] = 1, counts[1] + 1
    for widgets in doc["phases"].values():
        for w in widgets.values():
            w["days"] = {d: c for d, c in w["days"].items() if d >= cutoff}
    json_store.write(_path(), doc)


def learned(today: date) -> dict[str, Any]:
    """{on, phases: {phase: {widget: {score, tucked, seen_days, taps}}}}"""
    doc = load()
    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
    out: dict[str, dict[str, Any]] = {}
    for phase, widgets in doc["phases"].items():
        for widget, w in widgets.items():
            days = {d: c for d, c in w["days"].items() if d >= cutoff}
            seen = sum(1 for c in days.values() if c[0])
            taps = sum(c[1] for c in days.values())
            if not seen:
                continue
            out.setdefault(phase, {})[widget] = {"score": round(taps / seen, 2), "taps": taps, "seen_days": seen,
                                                 "tucked": bool(w.get("interactive")) and seen >= TUCK_AFTER_DAYS and taps == 0}
    return {"on": doc["on"], "phases": out}


def set_on(on: bool) -> None:
    doc = load()
    doc["on"] = on
    json_store.write(_path(), doc)
