"""Home that learns what you use (11.3).

Home tells SirisOS, per part of the day, which cards were shown (once a day each) and which you tapped. Over the last
four weeks:

- cards you tap rise within their section, more taps per day shown, higher;
- a card with something to tap (a button or a link) that's been shown on 10 or more days without one tap is tucked
  under "Show everything" for that part of the day. Cards there just to read (the weather) are never tucked;
- one tap on a tucked card (from Show everything) brings it straight back.

11.10: **where you go.** Each section you open (/gym, /tasks, /brief…) is counted once a day per part of the day. A
section you've opened on 3 or more days in the last four weeks at this part of the day is offered at the top of Home
("Usually now"), most-used first. The counts are also how SirisOS sees which sections go unused. Loading
placeholders are never counted as cards.

Turn it off on Customise Home. Kept in home-usage.json.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.services import json_store

KEEP_DAYS = 28
TUCK_AFTER_DAYS = 10
VISIT_KEEP_DAYS = 90
USUALLY_DAYS = 3  # opened on this many days at this part of the day in four weeks: offered on Home
NOT_PLACES = {"/", "/inbox", "/login"}
PHASES = ("morning", "work", "weekend", "evening", "winddown", "night")


def _path():
    return json_store.data_path("SIRISOS_HOME_USAGE_PATH", "home-usage.json")


def load() -> dict[str, Any]:
    doc = json_store.read(_path(), {}) or {}
    doc.setdefault("on", True)
    doc.setdefault("phases", {})
    doc.setdefault("visits", {})
    return doc


def record(events: list[dict[str, Any]], today: date) -> None:
    doc = load()
    day = today.isoformat()
    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
    for e in events[:200]:
        phase, widget, kind = e.get("phase"), str(e.get("widget") or "")[:80], e.get("kind")
        if kind == "visit":
            if phase in PHASES and widget.startswith("/") and widget not in NOT_PLACES:
                doc["visits"].setdefault(phase, {}).setdefault(widget, {})[day] = 1
            continue
        if phase not in PHASES or not widget or kind not in ("seen", "tap") or widget.startswith("loading-"):
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
        for gone in [k for k in widgets if k.startswith("loading-")]:
            widgets.pop(gone)  # 11.10: placeholders were counted as cards before
    keep = (today - timedelta(days=VISIT_KEEP_DAYS)).isoformat()
    for places in doc["visits"].values():
        for path in list(places):
            places[path] = {d: 1 for d in places[path] if d >= keep}
            if not places[path]:
                places.pop(path)
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
    usually: dict[str, list[dict[str, Any]]] = {}
    days_used: dict[str, set[str]] = {}
    for phase, places in doc["visits"].items():
        recent = {p: sum(1 for d in days if d >= cutoff) for p, days in places.items()}
        picks = sorted(((p, n) for p, n in recent.items() if n >= USUALLY_DAYS), key=lambda r: -r[1])[:4]
        if picks:
            usually[phase] = [{"path": p, "days": n} for p, n in picks]
        for p, days in places.items():
            days_used.setdefault(p, set()).update(d for d in days if d >= cutoff)
    return {"on": doc["on"], "phases": out, "usually": usually if doc["on"] else {},
            "sections": {p: len(d) for p, d in sorted(days_used.items())}}


def set_on(on: bool) -> None:
    doc = load()
    doc["on"] = on
    json_store.write(_path(), doc)
