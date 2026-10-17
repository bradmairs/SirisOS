"""CPD from the calendar: events that look like CPD (a webinar, course,
conference...) in the last and next 30 days, so they can be logged in
Engineers Australia (still the only record) without remembering them.

An event drops off the list once it's marked logged or "not CPD", or once
an Engineers Australia import has an activity on the same day with a
similar title.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timedelta
from typing import Any

from app.career import cpd
from app.career.store import CareerDocument

CPD_WORDS = re.compile(
    r"webinar|course|training|conference|workshop|seminar|symposium|\bcpd\b|lecture|masterclass|summit|"
    r"short course|tech(nical)? (talk|session)|lunch ?(and|&) ?learn|ipwea|\bawa\b|ozwater|engineers australia|"
    r"\bea\b|toastmasters|mentoring|site tour|forum|e-?learning|module|certificate|accreditation",
    re.I,
)
WINDOW_DAYS = 30
ALL_DAY_HOURS = 7.5


def key(event: dict[str, Any]) -> str:
    raw = f"{event.get('title', '')}|{event.get('start', '')}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def _day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def hours(event: dict[str, Any]) -> float:
    """Length in hours, to the nearest quarter; all-day events count as a working day."""
    if event.get("all_day"):
        start, end = _day(event.get("start")), _day(event.get("end"))
        days = max(1, (end - start).days) if start and end else 1
        return ALL_DAY_HOURS * days
    try:
        start = datetime.fromisoformat(str(event.get("start")))
        end = datetime.fromisoformat(str(event.get("end")))
    except (TypeError, ValueError):
        return 1.0
    return max(0.25, round((end - start).total_seconds() / 3600 * 4) / 4)


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}


def already_logged(doc: CareerDocument, event: dict[str, Any]) -> bool:
    day = _day(event.get("start"))
    words = _words(str(event.get("title", "")))
    for r in doc.cpd.records:
        if r.date and day and abs((date.fromisoformat(r.date) - day).days) <= 1:
            mine = _words(r.title)
            if words and mine and len(words & mine) / min(len(words), len(mine)) >= 0.5:
                return True
    return False


def suggestions(doc: CareerDocument, events: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    out = []
    for event in events:
        title = str(event.get("title") or "")
        text = f"{title} {event.get('location') or ''} {event.get('calendar') or ''}"
        if not CPD_WORDS.search(text):
            continue
        k = key(event)
        if k in doc.cpd.suggestions or already_logged(doc, event):
            continue
        day = _day(event.get("start"))
        out.append({
            "key": k,
            "title": title,
            "date": day.isoformat() if day else None,
            "upcoming": bool(day and day > today),
            "hours": hours(event),
            "category": cpd.guess_category(title, str(event.get("location") or "")),
            "location": event.get("location"),
            "calendar": event.get("calendar"),
        })
    return out


def window(today: date) -> tuple[date, date]:
    return today - timedelta(days=WINDOW_DAYS), today + timedelta(days=WINDOW_DAYS + 1)
