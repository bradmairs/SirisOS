"""6.3: proactive nudges: a free stretch when something's due, winding down for bed, capped and quiet at night."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.nudges import service
from app.push import store

TZ = ZoneInfo("Australia/Melbourne")
AT = datetime(2026, 11, 2, 13, 5, tzinfo=TZ)  # a Monday


def ev(start: str, end: str) -> dict:
    return {"start": f"2026-11-02T{start}:00+11:00", "end": f"2026-11-02T{end}:00+11:00"}


def test_a_free_stretch_with_something_due():
    [n] = service.pick(AT, events=[ev("12:00", "13:00"), ev("14:00", "15:00")], due=["Clean the dryer filter", "Call the plumber"],
                       bedtime=None, bedtime_text=None, sent_today=0)
    assert n["topic"] == "nudges" and n["title"] == "You've got 55 free minutes"
    assert n["body"] == "Clean the dryer filter is due (and 1 more). A good time for it?"
    # Busy now and for over an hour, nothing due, or a short gap: nothing.
    assert service.pick(AT, events=[ev("13:00", "15:00")], due=["x"], bedtime=None, bedtime_text=None, sent_today=0) == []
    assert service.pick(AT, events=[], due=[], bedtime=None, bedtime_text=None, sent_today=0) == []
    assert service.pick(AT, events=[ev("13:30", "14:00")], due=["x"], bedtime=None, bedtime_text=None, sent_today=0) == []


def test_capped_and_quiet_at_night():
    assert service.pick(AT, events=[], due=["x"], bedtime=None, bedtime_text=None, sent_today=2) == []
    late = AT.replace(hour=22, minute=30)
    assert service.pick(late, events=[], due=["x"], bedtime=None, bedtime_text=None, sent_today=0, quiet=(22, 7)) == []


def test_winding_down_half_an_hour_before_bed():
    [n] = service.pick(AT.replace(hour=21, minute=50), events=None, due=[], bedtime="22:15",
                       bedtime_text="Bed by 10:15 pm for your 6:30 am site visit.", sent_today=1)
    assert n["key"] == "nudge:2026-11-02:wind-down" and n["body"].startswith("Bed by 10:15 pm")
    assert service.pick(AT.replace(hour=21, minute=0), events=None, due=[], bedtime="22:15", bedtime_text=None, sent_today=0) == []


def test_old_subscriptions_with_everything_get_nudges():
    full = store._upgrade({"endpoint": "https://x", "topics": ["apps", "inbox", "brief", "career", "home"], "v": 2})
    picked = store._upgrade({"endpoint": "https://x", "topics": ["inbox"], "v": 2})
    assert "nudges" in full["topics"] and full["v"] == 3
    assert picked["topics"] == ["inbox"] and picked["v"] == 3
