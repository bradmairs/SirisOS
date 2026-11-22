"""11.6.1: five notes to check a week, picked on Sunday; checking them doesn't bring more until next Sunday."""

from __future__ import annotations

import asyncio
from datetime import date

from app.hub import review_week

SUNDAY = date(2026, 11, 22)


def queue(titles):
    asked = []

    async def fetch(n):
        asked.append(n)
        return [{"title": t, "card": f"{t} — x"} for t in titles][:n]

    return fetch, asked


def run(day, fetch):
    return [n["title"] for n in asyncio.run(review_week.this_week(day, fetch))]


def test_five_a_week_and_no_more_until_sunday():
    titles = [f"Note {i}" for i in range(12)]
    fetch, asked = queue(titles)
    assert run(SUNDAY, fetch) == titles[:5] and asked == [5]
    for t in titles[:4]:
        review_week.mark(t, "done")
        titles.remove(t)   # checked: it leaves SirisAI's queue, and the next ones move up there
    review_week.mark("Note 4", "later")
    fetch, asked = queue(titles)
    assert run(date(2026, 11, 25), fetch) == [] and asked == []   # done for the week: SirisAI isn't even asked
    assert run(date(2026, 11, 28), fetch) == []                    # Saturday: still nothing
    assert run(date(2026, 11, 29), fetch) == ["Note 4", "Note 5", "Note 6", "Note 7", "Note 8"]   # next Sunday


def test_a_note_checked_elsewhere_leaves_the_card():
    fetch, _ = queue(["A", "B", "C"])
    assert run(SUNDAY, fetch) == ["A", "B", "C"]
    fetch, _ = queue(["B", "C", "D"])   # A was checked in SirisAI's chat
    assert run(date(2026, 11, 23), fetch) == ["B", "C"]
