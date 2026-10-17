"""Past briefs, and what changed since the last one.

Each day's brief is kept (the last one built that day) in the data
directory for 60 days, so the Brief screen can scroll back. A new brief is
compared with the most recent earlier day's: warmer or colder, tasks that
appeared or cleared, apps that went down or came back, important email,
the Second Brain inbox, and CPD hours.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.services import json_store

KEEP_DAYS = 60


def _folder() -> Path:
    return json_store.data_path("SIRISOS_BRIEF_HISTORY_PATH", "brief-history")


def save(brief: dict[str, Any]) -> None:
    day = brief.get("date")
    if not day:
        return
    folder = _folder()
    json_store.write(folder / f"{day}.json", {k: v for k, v in brief.items() if k not in ("status", "changes")})
    cutoff = (date.fromisoformat(day) - timedelta(days=KEEP_DAYS)).isoformat()
    for old in folder.glob("*.json"):
        if old.stem < cutoff:
            old.unlink(missing_ok=True)


def load(day: str) -> dict[str, Any] | None:
    try:
        date.fromisoformat(day)
    except ValueError:
        return None
    return json_store.read(_folder() / f"{day}.json", None)


def days() -> list[dict[str, Any]]:
    """Every kept brief, newest first: its date, weekday and headline."""
    out = []
    folder = _folder()
    for path in sorted(folder.glob("*.json"), reverse=True) if folder.exists() else []:
        brief = json_store.read(path, None)
        if isinstance(brief, dict):
            out.append({"date": brief.get("date", path.stem), "weekday": brief.get("weekday", ""), "headline": (brief.get("headline") or [])[:3]})
    return out


def previous(day: str) -> dict[str, Any] | None:
    """The most recent kept brief from before `day`."""
    folder = _folder()
    earlier = sorted((p for p in folder.glob("*.json") if p.stem < day), reverse=True) if folder.exists() else []
    return json_store.read(earlier[0], None) if earlier else None


def _titles(items: list[dict[str, Any]] | None, key: str = "title") -> list[str]:
    return [str(i.get(key)) for i in items or [] if isinstance(i, dict) and i.get(key)]


def _plural(n: float, word: str) -> str:
    return f"{n:g} {word}{'' if n == 1 else 's'}"


def changes(prev: dict[str, Any] | None, cur: dict[str, Any]) -> dict[str, Any] | None:
    """What's different from the last brief, as short lines (None with no earlier brief)."""
    if not prev:
        return None
    lines: list[str] = []
    since = "yesterday" if prev.get("date") == (date.fromisoformat(cur["date"]) - timedelta(days=1)).isoformat() else f"{prev.get('weekday') or prev.get('date')}"

    p_high = ((prev.get("weather") or {}).get("today") or {}).get("high_c")
    c_high = ((cur.get("weather") or {}).get("today") or {}).get("high_c")
    if isinstance(p_high, (int, float)) and isinstance(c_high, (int, float)) and abs(c_high - p_high) >= 3:
        lines.append(f"{round(abs(c_high - p_high))}° {'warmer' if c_high > p_high else 'cooler'} than {since}.")

    p_tasks, c_tasks = set(_titles(prev.get("tasks"))), _titles(cur.get("tasks"))
    new_tasks = [t for t in c_tasks if t not in p_tasks]
    gone_tasks = [t for t in p_tasks if t not in set(c_tasks)]
    if new_tasks:
        lines.append(f"New to do: {', '.join(new_tasks[:3])}{'…' if len(new_tasks) > 3 else ''}.")
    if gone_tasks:
        lines.append(f"Off the list: {', '.join(sorted(gone_tasks)[:3])}{'…' if len(gone_tasks) > 3 else ''}.")

    p_apps = {a["name"]: a.get("state") for a in prev.get("apps_attention") or [] if isinstance(a, dict) and a.get("name")}
    c_apps = {a["name"]: a.get("state") for a in cur.get("apps_attention") or [] if isinstance(a, dict) and a.get("name")}
    for name, state in c_apps.items():
        if p_apps.get(name) != state:
            lines.append(f"{name} is {state} now.")
    for name in p_apps:
        if name not in c_apps:
            lines.append(f"{name} is working again.")

    p_mail = len(((prev.get("email") or {}).get("important")) or [])
    c_mail = len(((cur.get("email") or {}).get("important")) or [])
    if c_mail > p_mail:
        lines.append(f"{_plural(c_mail - p_mail, 'more important email')} than {since}.")

    p_inbox = (prev.get("brain") or {}).get("inbox") or 0
    c_inbox = (cur.get("brain") or {}).get("inbox") or 0
    if c_inbox != p_inbox:
        diff = c_inbox - p_inbox
        lines.append(f"Second Brain inbox {'up' if diff > 0 else 'down'} {abs(diff)} (now {c_inbox}).")

    p_cpd = (((prev.get("career") or {}).get("cpd")) or {}).get("total")
    c_cpd = (((cur.get("career") or {}).get("cpd")) or {}).get("total")
    if isinstance(p_cpd, (int, float)) and isinstance(c_cpd, (int, float)) and c_cpd != p_cpd:
        lines.append(f"CPD {'up' if c_cpd > p_cpd else 'down'} {abs(c_cpd - p_cpd):g} hours since {since} (now {c_cpd:g}).")

    return {"since": prev.get("date"), "label": since, "lines": lines}
