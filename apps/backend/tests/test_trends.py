"""4.1: the year at a glance, and the daily log behind it."""

from __future__ import annotations

from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.career import store as career_store
from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from app.tasks import service as tasks
from app.tasks import store as task_store
from app.trends import log, service
from tests.test_hub import AUTH, ENV

TODAY = tasks.today()
health_days: list[int] = []


def handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/siris/hub/v1/health/days":
        n = int(request.url.params["days"])
        health_days.append(n)
        if n > 35:
            return httpx.Response(422)  # an older SirisAI
        return httpx.Response(200, json={"guest_mode": False, "days": [
            {"date": TODAY.isoformat(), "metrics": {"running_km": 5.0, "exercise_minutes": 40, "steps": 8000}},
            {"date": (TODAY - timedelta(days=1)).isoformat(), "metrics": {"running_km": 3.2, "steps": 10000}}]})
    if path_ok(request):
        return httpx.Response(200, json={"items": [], "counts": {"open": 0, "urgent": 0}})
    return httpx.Response(404)


def path_ok(request):
    return request.url.path == "/siris/hub/v1/attention"


@pytest.fixture
def client(monkeypatch, tmp_path):
    for env, name in (("SIRISOS_TASKS_PATH", "tasks.json"), ("SIRISOS_TRENDS_PATH", "trends.json"), ("SIRISOS_WRAPUP_PATH", "w.json"),
                      ("SIRISOS_CAREER_PATH", "career.json"), ("SIRISOS_ATTENTION_STATE_PATH", "a.json"), ("SIRISOS_REVIEW_PATH", "r.json")):
        monkeypatch.setenv(env, str(tmp_path / name))
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    health_days.clear()
    reset_hub(ENV)
    yield TestClient(app)


def test_months_and_streaks():
    assert service.months_back(date(2026, 2, 10), 3) == ["2025-12", "2026-01", "2026-02"]
    d = date(2026, 10, 23)
    days = {"2026-10-20", "2026-10-21", "2026-10-22", "2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04"}
    assert service.streaks(days, d) == {"current": 3, "longest": 4}  # tonight's wrap-up not done yet
    assert service.streaks(days | {"2026-10-23"}, d)["current"] == 4
    assert service.streaks(set(), d) == {"current": 0, "longest": 0}


def test_daily_log_keeps_the_busiest_inbox_and_counts(client):
    log.inbox(3)
    log.inbox(1)
    log.task_done()
    log.task_done()
    log.mark("journal")
    log.mark("journal")
    assert log.days()[TODAY.isoformat()] == {"inbox": 3, "tasks_done": 2, "journal": True}


def test_completing_a_task_is_logged(client):
    task_store.save(task_store.TasksDocument(tasks=[task_store.Task(id="a", title="Bins")]))
    assert client.post("/api/v1/tasks/sirisos:a/done", headers=AUTH, json={}).status_code == 200
    assert log.days()[TODAY.isoformat()]["tasks_done"] == 1


def test_the_year(client):
    this_month = TODAY.isoformat()[:7]
    doc = career_store.load()
    doc.cpd.records = [career_store.CpdRecord(id="1", date=TODAY.isoformat(), hours=2.5, title="Webinar"),
                       career_store.CpdRecord(id="2", date=(TODAY - timedelta(days=500)).isoformat(), hours=9, title="Old")]
    career_store.save(doc)
    old = (TODAY - timedelta(days=40)).isoformat()  # done tasks are kept 60 days
    task_store.save(task_store.TasksDocument(tasks=[task_store.Task(id="a", title="Old one", done_at=f"{old}T10:00:00")]))
    log.inbox(4)
    log.task_done()
    log.mark("journal")
    log.mark("journal", TODAY - timedelta(days=1))
    body = client.get("/api/v1/trends", headers=AUTH).json()
    assert len(body["months"]) == 12 and body["months"][-1]["month"] == this_month
    now = body["months"][-1]
    assert now["cpd_hours"] == 2.5 and now["tasks_done"] == 1 and now["inbox"] == 4 and now["journal_days"] >= 1
    assert sum(m["tasks_done"] for m in body["months"]) == 2  # the old done task, from before the log
    assert sum(m["running_km"] for m in body["months"]) == 8.2
    assert body["journal"]["current"] == 2
    assert health_days[0] > 300 and health_days[-1] == 35  # fell back for an older SirisAI
    assert body["cpd"]["required"] == 150
