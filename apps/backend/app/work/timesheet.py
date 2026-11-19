"""Rough timesheet notes (9.8): what you worked on and for how long, jotted as
you go, to fill in the real timesheet from at the end of the day or week.

Kept in timesheet.json (SIRISOS_TIMESHEET_PATH). Each entry is a day, what it
was, the hours, and an optional job or project code. Typing "Pump station
review 1.5h" (or "90 min", "1:30") is enough: the time is taken out of the words.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, timedelta
from typing import Any

from app.services import json_store

MAX_ENTRIES = 5000
# "1.5h", "1.5 hrs", "2 hours", "90 min", "1h30", "1:30"
_TIME = re.compile(
    r"(?<![\w.])(?:(?P<h>\d+(?:\.\d+)?)\s*(?:hours|hour|hrs|hr|h)(?![a-z])\s*(?:(?P<hm>\d{1,2})\s*(?:mins|min|m)?\b)?"
    r"|(?P<m>\d+)\s*(?:m|min|mins|minutes)\b|(?P<ch>\d{1,2}):(?P<cm>[0-5]\d)\b)",
    re.I,
)


def _path():
    return json_store.data_path("SIRISOS_TIMESHEET_PATH", "timesheet.json")


def load() -> list[dict[str, Any]]:
    return list(json_store.read(_path(), {}).get("entries") or [])


def save(entries: list[dict[str, Any]]) -> None:
    json_store.write(_path(), {"entries": entries[-MAX_ENTRIES:]})


def parse(text: str) -> tuple[str, float | None]:
    """The words without the time, and the time in hours (None when there isn't one)."""
    m = _TIME.search(text)
    if not m:
        return text.strip(), None
    if m.group("h"):
        hours = float(m.group("h")) + (int(m.group("hm")) / 60 if m.group("hm") else 0)
    elif m.group("m"):
        hours = int(m.group("m")) / 60
    else:
        hours = int(m.group("ch")) + int(m.group("cm")) / 60
    what = (text[:m.start()] + text[m.end():]).strip(" -–,;:")
    return re.sub(r"\s{2,}", " ", what), round(hours, 2)


def monday(on: date) -> date:
    return on - timedelta(days=on.weekday())


def week(on: date) -> dict[str, Any]:
    """The week containing `on`: each day's entries and total, the week's total, and per code."""
    start = monday(on)
    days = [start + timedelta(days=i) for i in range(7)]
    entries = [e for e in load() if start.isoformat() <= e["date"] <= days[-1].isoformat()]
    by_code: dict[str, float] = {}
    for e in entries:
        key = e.get("code") or "No code"
        by_code[key] = round(by_code.get(key, 0) + e["hours"], 2)
    out_days = []
    for d in days:
        mine = [e for e in entries if e["date"] == d.isoformat()]
        out_days.append({"date": d.isoformat(), "entries": mine, "hours": round(sum(e["hours"] for e in mine), 2)})
    return {"week_of": start.isoformat(), "days": out_days, "hours": round(sum(e["hours"] for e in entries), 2),
            "by_code": [{"code": k, "hours": v} for k, v in sorted(by_code.items(), key=lambda kv: -kv[1])],
            "text": as_text(out_days)}


def as_text(days: list[dict[str, Any]]) -> str:
    """The week as plain lines, to paste into the real timesheet."""
    lines = []
    for d in days:
        if not d["entries"]:
            continue
        lines.append(f"{date.fromisoformat(d['date']):%a %d %b} ({_h(d['hours'])})")
        for e in d["entries"]:
            lines.append(f"  {_h(e['hours'])}  {e['what']}" + (f" [{e['code']}]" if e.get("code") else ""))
    return "\n".join(lines)


def _h(hours: float) -> str:
    return f"{hours:g} h"


def add(what: str, hours: float | None, on: date, code: str = "") -> dict[str, Any]:
    words, parsed = parse(what)
    hours = hours if hours is not None else parsed
    if hours is None or hours <= 0:
        raise ValueError("How long was it? Add the hours, or put them in the words (e.g. 1.5h or 90 min).")
    if hours > 24:
        raise ValueError("That's more than a day.")
    entry = {"id": uuid.uuid4().hex[:10], "date": on.isoformat(), "what": words or "Work", "hours": round(hours, 2), "code": code.strip()[:40]}
    entries = load()
    entries.append(entry)
    save(entries)
    return entry


def change(entry_id: str, **fields: Any) -> dict[str, Any] | None:
    entries = load()
    found = next((e for e in entries if e["id"] == entry_id), None)
    if found is None:
        return None
    for k in ("what", "code", "date"):
        if fields.get(k) is not None:
            found[k] = str(fields[k]).strip()
    if fields.get("hours") is not None:
        if not 0 < fields["hours"] <= 24:
            raise ValueError("Hours must be between 0 and 24.")
        found["hours"] = round(float(fields["hours"]), 2)
    save(entries)
    return found


def remove(entry_id: str) -> bool:
    entries = load()
    kept = [e for e in entries if e["id"] != entry_id]
    if len(kept) == len(entries):
        return False
    save(kept)
    return True


def codes() -> list[str]:
    """Codes used before, most recent first, for picking again."""
    seen: list[str] = []
    for e in reversed(load()):
        c = e.get("code")
        if c and c not in seen:
            seen.append(c)
    return seen[:12]
