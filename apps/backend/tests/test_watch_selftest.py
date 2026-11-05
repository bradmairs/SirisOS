"""SirisAI going quiet, and the morning's self-test (7.0)."""

from datetime import datetime, timedelta, timezone

import pytest

from app import selftest
from app.hub import watch
from app.verify import Result

NOW = datetime(2026, 11, 5, 6, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def fresh(monkeypatch, tmp_path):
    monkeypatch.setattr(watch, "_silent_since", None)
    monkeypatch.setenv("SIRISOS_SELFTEST_PATH", str(tmp_path / "selftest.json"))


def test_one_alert_after_three_minutes_and_gone_when_it_answers():
    watch.record(False, NOW)
    assert watch.items(NOW + timedelta(minutes=2)) == []
    first = watch.items(NOW + timedelta(minutes=3))
    later = watch.items(NOW + timedelta(minutes=30))
    assert first[0]["title"] == "SirisAI isn't answering" and first[0]["severity"] == "attention"
    assert first[0]["key"] == later[0]["key"], "the same outage, so it's sent once"
    watch.record(False, NOW + timedelta(minutes=9))
    assert watch.items(NOW + timedelta(minutes=9))[0]["key"] == first[0]["key"]
    watch.record(True)
    assert watch.items(NOW + timedelta(minutes=30)) == []


def test_due_once_a_day_after_five():
    at = lambda h: datetime(2026, 11, 5, h, 0)  # noqa: E731
    assert not selftest.due(at(4), None)
    assert selftest.due(at(5), None)
    assert selftest.due(at(6), {"day": "2026-11-04"})
    assert not selftest.due(at(6), {"day": "2026-11-05"})


def test_broken_reaches_the_inbox_loudly_and_a_look_quietly():
    from app.services import json_store

    results = [Result("Apps", "ok"), Result("Daily brief", "fail", "no reply"), Result("Security", "warn", "weak password")]
    json_store.write(selftest._path(), selftest.summarise(results, "2026-11-05", "2026-11-05T05:00:00+00:00"))
    broken, look = selftest.items()
    assert broken["severity"] == "attention" and "Daily brief: no reply" in broken["body"] and broken["key"].endswith("2026-11-05")
    assert look["severity"] == "info" and "weak password" in look["body"]
    json_store.write(selftest._path(), selftest.summarise(results, "2026-11-06", "2026-11-06T05:00:00+00:00"))
    assert selftest.items()[1]["key"] == look["key"], "a dismissal holds until the list changes"
    assert selftest.items()[0]["key"] != broken["key"], "broken comes back each day"


def test_all_fine_says_nothing():
    from app.services import json_store

    json_store.write(selftest._path(), selftest.summarise([Result("Apps", "ok")], "2026-11-05", "x"))
    assert selftest.items() == []
