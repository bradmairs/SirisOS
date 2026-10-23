"""3.8: buttons on phone notifications, and the /act page behind a tap."""

from __future__ import annotations

from datetime import datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from app.attention import service as attention
from app.brief.service import zone
from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from app.push import actions, notifier
from app.tasks import store as task_store
from tests.test_hub import ENV

acted: list[tuple[str, dict]] = []


def handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/siris/hub/v1/attention/42/act":
        import json

        acted.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"item": {"id": 42, "title": "Run backup", "status": "done"}, "result": "ok"})
    return httpx.Response(404)


@pytest.fixture
def client(monkeypatch, tmp_path):
    for env, name in (("SIRISOS_TASKS_PATH", "tasks.json"), ("SIRISOS_PUSH_ACTIONS_PATH", "used.json"), ("SIRISOS_ATTENTION_STATE_PATH", "a.json")):
        monkeypatch.setenv(env, str(tmp_path / name))
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    acted.clear()
    reset_hub(ENV)
    yield TestClient(app)


def token_for(target: str, buttons: list[dict], **kw) -> str:
    return actions.sign(target, buttons, "Call the plumber", "Due now", "/tasks", **kw)


def test_tokens_are_signed_and_run_out():
    t = token_for("task:sirisos:abc", actions.for_task("abc"))
    assert actions.verify(t)["t"] == "task:sirisos:abc"
    raw, mac = t.split(".")
    with pytest.raises(actions.BadToken):
        actions.verify(raw[:-2] + "xx." + mac)
    with pytest.raises(actions.BadToken, match="two days"):
        actions.verify(token_for("task:x", [], now=1_000_000))


def test_inbox_buttons_skip_risky_actions():
    item = {"actions": [{"id": "lockdown", "label": "Lock down", "style": "danger"},
                        {"id": "send", "label": "Send", "style": "primary", "confirm": "Send it?"},
                        {"id": "approve", "label": "Approve", "style": "primary"}]}
    assert [a["id"] for a in actions.for_inbox(item)] == ["approve", "snooze"]
    assert [a["id"] for a in actions.for_inbox({"actions": []})] == ["snooze", "dismiss"]


def test_payload_carries_buttons_and_the_act_link():
    msg = notifier.inbox_messages([{"id": "ai:42", "severity": "urgent", "source": "siris", "title": "Approve?", "body": "",
                                    "actions": [{"id": "approve", "label": "Approve", "style": "primary"}]}])[0]
    payload = notifier.payload_for(msg)
    assert payload["actions"] == [{"action": "approve", "title": "Approve"}, {"action": "snooze", "title": "Snooze 3 h"}]
    assert payload["url"].startswith("/act?t=")
    assert actions.verify(payload["url"][len("/act?t="):])["t"] == "inbox:ai:42"
    brief = notifier.payload_for(notifier.message("brief:x", "brief", "Your brief"))
    assert "actions" not in brief and brief["url"] == "/"


def test_done_from_a_notification_works_once(client):
    doc = task_store.load()
    doc.tasks.append(task_store.Task(id="abc", title="Call the plumber", due="2026-10-23", time="09:00"))
    task_store.save(doc)
    t = token_for("task:sirisos:abc", actions.for_task("abc"))
    seen = client.get("/api/v1/push/act", params={"t": t}).json()
    assert seen["title"] == "Call the plumber" and [a["id"] for a in seen["actions"]] == ["done", "later"] and seen["done"] is None
    r = client.post("/api/v1/push/act", json={"token": t, "action": "done"})
    assert r.status_code == 200 and r.json()["message"] == "Done."
    assert task_store.load().tasks[0].done_at
    again = client.post("/api/v1/push/act", json={"token": t, "action": "later"})
    assert again.status_code == 409 and "Already done" in again.json()["detail"]
    assert client.get("/api/v1/push/act", params={"t": t}).json()["done"] == "done"


def test_in_an_hour_moves_the_task_and_rearms_it(client):
    doc = task_store.load()
    doc.tasks = [task_store.Task(id="abc", title="Call", due="2026-10-23", time="09:00", reminded_for="2026-10-23T09:00")]
    task_store.save(doc)
    assert actions.later("sirisos:abc", datetime(2026, 10, 23, 23, 30, tzinfo=zone())) == "Moved to 00:30."
    t = task_store.load().tasks[0]
    assert (t.due, t.time, t.reminded_for) == ("2026-10-24", "00:30", None)


def test_inbox_buttons_relay_and_snooze(client):
    t = token_for("inbox:ai:42", [{"id": "approve", "title": "Approve"}, {"id": "snooze", "title": "Snooze 3 h"}])
    r = client.post("/api/v1/push/act", json={"token": t, "action": "approve"})
    assert r.json()["message"] == "Approve: done."
    assert acted == [("/siris/hub/v1/attention/42/act", {"action": "approve"})]
    s = token_for("inbox:os:app:archive:down", actions.for_inbox({}))
    assert client.post("/api/v1/push/act", json={"token": s, "action": "snooze"}).json()["message"] == "Snoozed for 3 hours."
    assert "os:app:archive:down" in attention.snoozed()


def test_bad_tokens_and_buttons_are_refused(client):
    assert client.get("/api/v1/push/act", params={"t": "nope.nope"}).status_code == 403
    t = token_for("task:sirisos:abc", actions.for_task("abc"))
    assert client.post("/api/v1/push/act", json={"token": t, "action": "dismiss"}).status_code == 403
    assert client.post("/api/v1/push/act", json={"token": t, "action": "done"}).status_code == 404  # no such task


def test_the_approval_pin_goes_through(client, monkeypatch):
    """SirisAI 2.46's approval PIN: its 403 reaches the app, and the PIN is relayed."""
    sent: list[dict] = []

    def pin_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/siris/hub/v1/attention/7/act":
            import json

            body = json.loads(request.content)
            sent.append(body)
            if body.get("pin") != "4321":
                return httpx.Response(403, json={"detail": "pin_required: approving this needs your PIN" if "pin" not in body else "Wrong PIN. 4 more and big approvals lock for 10 minutes."})
            return httpx.Response(200, json={"item": {"id": 7, "title": "2 updates", "status": "done"}, "result": "ok"})
        return httpx.Response(404)

    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(pin_handler))
    reset_hub(ENV)
    from tests.test_hub import AUTH

    held = client.post("/api/v1/attention/ai:7/act", headers=AUTH, json={"action": "install"})
    assert held.status_code == 403 and "pin_required" in held.json()["detail"]
    wrong = client.post("/api/v1/attention/ai:7/act", headers=AUTH, json={"action": "install", "pin": "0000"})
    assert wrong.status_code == 403 and "Wrong PIN" in wrong.json()["detail"]
    assert client.post("/api/v1/attention/ai:7/act", headers=AUTH, json={"action": "install", "pin": "4321"}).status_code == 200
    assert sent == [{"action": "install"}, {"action": "install", "pin": "0000"}, {"action": "install", "pin": "4321"}]

    t = token_for("inbox:ai:7", [{"id": "install", "title": "Install updates"}])
    assert "pin_required" in client.post("/api/v1/push/act", json={"token": t, "action": "install"}).json()["detail"]
    assert client.post("/api/v1/push/act", json={"token": t, "action": "install", "pin": "4321"}).json()["message"] == "Install updates: done."
