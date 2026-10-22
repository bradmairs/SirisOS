"""Tasks (2.9): parsing "remind me…", one list from SirisOS, Siris notes and
SirisAI reminders, ticking each where it lives, snoozing, repeats, and the
push reminder when a task's time comes."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.brief.service import zone
from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from app.push import notifier
from app.tasks import service, store
from tests.test_hub import AUTH, ENV

WED = date(2026, 10, 21)


@pytest.mark.parametrize("text,title,due,at,repeat", [
    ("remind me to call the plumber tomorrow at 9am", "Call the plumber", "2026-10-22", "09:00", "none"),
    ("Remind me to pay rego on Friday", "Pay rego", "2026-10-23", None, "none"),
    ("remind me to take the bins out tonight", "Take the bins out", "2026-10-21", "19:00", "none"),
    ("remind me to log CPD every week", "Log CPD", "2026-10-21", None, "weekly"),
    ("todo: renew passport 3/11", "Renew passport", "2026-11-03", None, "none"),
    ("remind me to email Dana at 17:30", "Email Dana", "2026-10-21", "17:30", "none"),
    ("remind me to stretch on weekdays", "Stretch", "2026-10-21", None, "weekdays"),
    ("remind me to read the AS 3500 update", "Read the AS 3500 update", None, None, "none"),
    ("remind me to book the dentist next week", "Book the dentist", "2026-10-26", None, "none"),
])
def test_parse_remind_me(text, title, due, at, repeat):
    t = service.parse(text, on=WED)
    assert (t.title, t.due, t.time, t.repeat) == (title, due, at, repeat)
    assert service.is_task_text(text) or text.startswith("todo")


def test_repeats_move_to_the_next_date():
    assert store.next_due(date(2026, 10, 23), "weekdays") == date(2026, 10, 26)  # Friday -> Monday
    assert store.next_due(date(2026, 1, 31), "monthly") == date(2026, 2, 28)
    assert store.next_due(date(2026, 12, 15), "monthly") == date(2027, 1, 15)
    assert store.next_due(date(2026, 10, 21), "fortnightly") == date(2026, 11, 4)


class FakeSirisAI:
    def __init__(self) -> None:
        self.vault = [{"task": "Send levels to Dana", "note": "Werribee Drainage", "due": (date.today() - timedelta(days=2)).isoformat(), "type": "project"},
                      {"task": "Read the stormwater guide", "note": "Learning", "due": None, "type": "note"}]
        self.reminders = [{"id": 7, "message": "Call Mum", "due_at": (datetime.utcnow() + timedelta(hours=3)).isoformat(timespec="seconds") + "Z", "status": "pending"}]
        self.posts: list[tuple[str, dict]] = []
        self.down = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("down")
        path = request.url.path
        if request.method == "POST":
            self.posts.append((path, json.loads(request.content or b"{}")))
            if path == "/siris/brain/done":
                return httpx.Response(200, json={"action": "done", "note": "Werribee Drainage", "task": "Send levels to Dana"})
            if path == "/siris/hub/v1/reminders/7/done":
                return httpx.Response(200, json={"id": 7, "status": "cancelled"})
        if path == "/siris/brain/tasks":
            return httpx.Response(200, json={"tasks": self.vault})
        if path == "/siris/hub/v1/reminders":
            return httpx.Response(200, json={"guest_mode": False, "reminders": self.reminders})
        return httpx.Response(404, json={"detail": "Not Found"})


@pytest.fixture
def ai(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_TASKS_PATH", str(tmp_path / "tasks.json"))
    fake = FakeSirisAI()
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(fake))
    reset_hub(ENV)
    yield fake
    reset_hub({})


@pytest.fixture
def client():
    return TestClient(app)


def test_one_list_from_every_source(client, ai):
    assert client.get("/api/v1/tasks").status_code == 401
    made = client.post("/api/v1/tasks", headers=AUTH, json={"text": "remind me to put the bins out today at 7pm"}).json()
    assert made["title"] == "Put the bins out" and made["time"] == "19:00"
    client.post("/api/v1/tasks", headers=AUTH, json={"title": "Plan the garden"})
    body = client.get("/api/v1/tasks", headers=AUTH).json()
    assert body["sources"] == {"siris": True, "reminders": True}
    assert [t["title"] for t in body["groups"]["overdue"]] == ["Send levels to Dana"]
    assert body["groups"]["overdue"][0]["source"] == "siris" and body["groups"]["overdue"][0]["detail"] == "Werribee Drainage"
    today_titles = [t["title"] for t in body["groups"]["today"] + body["groups"]["week"]]
    assert "Put the bins out" in today_titles and "Call Mum" in today_titles
    assert {t["title"] for t in body["groups"]["someday"]} == {"Plan the garden", "Read the stormwater guide"}


def test_sirisai_down_still_shows_sirisos_tasks(client, ai):
    ai.down = True
    client.post("/api/v1/tasks", headers=AUTH, json={"title": "Plan the garden"})
    body = client.get("/api/v1/tasks", headers=AUTH).json()
    assert body["sources"] == {"siris": False, "reminders": False} and body["counts"]["someday"] == 1


def test_ticking_each_kind_where_it_lives(client, ai):
    own = client.post("/api/v1/tasks", headers=AUTH, json={"title": "Plan the garden"}).json()
    assert client.post(f"/api/v1/tasks/sirisos:{own['id']}/done", headers=AUTH).json() == {"id": f"sirisos:{own['id']}", "action": "done"}
    assert client.get("/api/v1/tasks", headers=AUTH).json()["counts"]["someday"] == 1  # only the vault one left
    assert service.done_today()[0]["title"] == "Plan the garden"

    r = client.post("/api/v1/tasks/siris:Werribee Drainage|Send levels to Dana/done", headers=AUTH)
    assert r.json()["action"] == "done" and ai.posts[-1] == ("/siris/brain/done", {"note": "Werribee Drainage", "task": "Send levels to Dana"})
    assert client.post("/api/v1/tasks/reminder:7/done", headers=AUTH).json()["action"] == "done"
    assert ai.posts[-1][0] == "/siris/hub/v1/reminders/7/done"
    assert client.post("/api/v1/tasks/sirisos:nope/done", headers=AUTH).status_code == 404


def test_a_repeating_task_moves_on_instead_of_finishing(client, ai):
    made = client.post("/api/v1/tasks", headers=AUTH, json={"title": "Log CPD", "repeat": "weekly", "due": service.today().isoformat()}).json()
    r = client.post(f"/api/v1/tasks/sirisos:{made['id']}/done", headers=AUTH).json()
    assert r["action"] == "repeated" and r["next_due"] == (service.today() + timedelta(days=7)).isoformat()


def test_snoozing_moves_a_task_and_leaves_notes_alone(client, ai):
    r = client.post("/api/v1/tasks/siris:Werribee Drainage|Send levels to Dana/snooze", headers=AUTH, json={"until": "next-week"})
    assert r.status_code == 200
    body = client.get("/api/v1/tasks", headers=AUTH).json()
    moved = next(t for g in body["groups"].values() for t in g if t["title"] == "Send levels to Dana")
    assert moved["group"] in ("week", "later") and moved["snoozed_until"] == r.json()["snoozed_until"]
    assert not any(p[0] == "/siris/brain/done" for p in ai.posts)
    own = client.post("/api/v1/tasks", headers=AUTH, json={"title": "Wash the car", "due": service.today().isoformat()}).json()
    client.post(f"/api/v1/tasks/sirisos:{own['id']}/snooze", headers=AUTH, json={"until": "tomorrow"})
    assert store.load().tasks[-1].due == (service.today() + timedelta(days=1)).isoformat()
    assert client.post(f"/api/v1/tasks/sirisos:{own['id']}/snooze", headers=AUTH, json={"until": "someday"}).status_code == 422


def test_editing_and_deleting_own_tasks(client, ai):
    own = client.post("/api/v1/tasks", headers=AUTH, json={"title": "Wash the car"}).json()
    r = client.patch(f"/api/v1/tasks/sirisos:{own['id']}", headers=AUTH, json={"title": "Wash both cars", "due": "2026-12-01"})
    assert r.json()["title"] == "Wash both cars" and r.json()["due"] == "2026-12-01"
    assert client.patch("/api/v1/tasks/siris:x|y", headers=AUTH, json={"title": "z"}).status_code == 404
    assert client.delete(f"/api/v1/tasks/sirisos:{own['id']}", headers=AUTH).json() == {"removed": True}
    assert client.post("/api/v1/tasks", headers=AUTH, json={"title": "  "}).status_code == 422


def test_a_task_with_a_time_is_pushed_once(ai):
    now = datetime.now(zone()).replace(second=0, microsecond=0)
    t = service.add(store.Task(title="Call the plumber", due=now.date().isoformat(), time=now.strftime("%H:%M")))
    msgs = notifier.task_messages(now + timedelta(minutes=1))
    assert [m["title"] for m in msgs] == ["Call the plumber"] and msgs[0]["url"] == "/tasks" and msgs[0]["topic"] == "inbox"
    assert notifier.task_messages(now + timedelta(minutes=2)) == []
    assert t.id in {x.id for x in store.load().tasks}


def test_remind_me_from_the_shortcut_adds_a_task(client, ai, monkeypatch):
    from app.shortcuts import keys

    monkeypatch.setenv("SIRISOS_SHORTCUT_KEYS_PATH", str(store._path().with_name("keys.json")))
    _, secret = keys.create("Test", ["capture"])
    r = client.post("/api/v1/shortcuts/capture", headers={"Authorization": f"Bearer {secret}"}, content="remind me to pay rego on Friday")
    assert r.status_code == 200 and r.text.startswith("Added to your tasks: “Pay rego” for ")
    assert not ai.posts  # nothing sent to Siris
