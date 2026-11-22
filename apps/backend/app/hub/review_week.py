"""This week's "Is this right?" notes (11.6.1).

The Home card used to ask SirisAI for the top 5 unchecked notes every time, so checking five just let the next five
move up and the card never went away. Now five are picked each Sunday and kept for the week. A note leaves the batch
when it's checked (here or anywhere else, since it then drops out of SirisAI's queue) or put off with "Not now".
When all five are done, the card is gone until next Sunday. Kept in review-week.json (SIRISOS_REVIEW_WEEK_PATH).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from typing import Any

from app.services import json_store

PER_WEEK = 5
LOOK_AHEAD = 20   # how much of SirisAI's queue is read to see which of the week's notes are still unchecked


def _path():
    return json_store.data_path("SIRISOS_REVIEW_WEEK_PATH", "review-week.json")


def week_of(day: date) -> str:
    """The Sunday the week starts on, on or before `day`."""
    return (day - timedelta(days=(day.weekday() + 1) % 7)).isoformat()


def _read() -> dict[str, Any]:
    return json_store.read(_path(), {}) or {}


async def this_week(today: date, fetch: Callable[[int], Awaitable[list[dict[str, Any]]]]) -> list[dict[str, Any]]:
    """The week's notes still waiting. `fetch(count)` reads SirisAI's queue (most connected unchecked first)."""
    doc = _read()
    week = week_of(today)
    if doc.get("week") != week:
        picked = (await fetch(PER_WEEK))[:PER_WEEK]
        doc = {"week": week, "picked": [n.get("title") for n in picked if n.get("title")], "done": [], "later": []}
        json_store.write(_path(), doc)
        fresh = picked
    else:
        waiting = [t for t in doc.get("picked", []) if t not in doc.get("done", []) and t not in doc.get("later", [])]
        if not waiting:
            return []   # done for the week: nothing is asked for again until Sunday
        fresh = await fetch(LOOK_AHEAD)
    gone = set(doc.get("done", [])) | set(doc.get("later", []))
    by_title = {n.get("title"): n for n in fresh}
    # A note checked somewhere else has left SirisAI's queue: it's done here too.
    return [by_title[t] for t in doc.get("picked", []) if t in by_title and t not in gone]


def mark(title: str, how: str) -> None:
    """`done` (checked or fixed) or `later` (Not now): either way it leaves this week's card."""
    doc = _read()
    if title in doc.get("picked", []) and title not in doc.get(how, []):
        doc.setdefault(how, []).append(title)
        json_store.write(_path(), doc)
