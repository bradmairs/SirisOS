"""9.51: no work tasks or work reminders at the weekend."""

import asyncio
from datetime import date, datetime

import pytest

pytestmark = pytest.mark.weekend

from app.brief.service import zone
from app.tasks import service, store


@pytest.fixture
def tasks(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_TASKS_PATH", str(tmp_path / "tasks.json"))
    doc = store.TasksDocument()
    doc.tasks = [store.Task(id="w1", title="Send the drainage report", due="2026-11-13", area="work"),
                 store.Task(id="w2", title="Call the client", due="2026-11-14", time="10:00", area="work"),
                 store.Task(id="p1", title="Mow the lawn", due="2026-11-14", time="10:00", area="personal")]
    store.save(doc)


def test_work_tasks_stay_out_of_the_weekend(tasks):
    saturday, monday = date(2026, 11, 14), date(2026, 11, 16)
    sat = asyncio.run(service.collect(None, saturday))
    titles = [t["title"] for g in sat["groups"].values() for t in g]
    assert titles == ["Mow the lawn"] and sat["hidden_work"] == 2 and sat["weekend"]
    everything = asyncio.run(service.collect(None, saturday, include_work=True))
    assert sum(everything["counts"].values()) == 3 and everything["hidden_work"] == 0
    mon = asyncio.run(service.collect(None, monday))
    assert sum(mon["counts"].values()) == 3 and mon["hidden_work"] == 0 and not mon["weekend"]


def test_no_work_reminders_at_the_weekend(tasks):
    at = datetime(2026, 11, 14, 10, 5, tzinfo=zone())
    assert [t.id for t in service.due_now(at)] == ["p1"]
