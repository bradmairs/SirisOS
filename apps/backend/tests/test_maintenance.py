"""5.2: home maintenance jobs and appliances, in the house's rooms."""

from __future__ import annotations

import json
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.maintenance import service
from app.push import actions, store as push_store
from app.tasks import service as tasks
from tests.test_hub import AUTH

TODAY = date(2026, 10, 29)


@pytest.fixture
def client(monkeypatch, tmp_path):
    for env, name in (("SIRISOS_MAINTENANCE_PATH", "m.json"), ("SIRISOS_PUSH_ACTIONS_PATH", "used.json"),
                      ("SIRISOS_PUSH_SUBSCRIPTIONS_PATH", "subs.json")):
        monkeypatch.setenv(env, str(tmp_path / name))
    monkeypatch.setattr(tasks, "today", lambda: TODAY)
    return TestClient(app)


def test_starters_wait_until_you_say_when_you_last_did_them(client):
    body = client.get("/api/v1/maintenance", headers=AUTH).json()
    assert len(body["jobs"]) == len(service.STARTERS) and all(j["state"] == "unset" for j in body["jobs"])
    assert body["summary"]["rooms"] == [] and body["summary"]["unset"] == len(service.STARTERS)
    # Seeded once: deleting one keeps it deleted.
    first = body["jobs"][0]["id"]
    client.delete(f"/api/v1/maintenance/jobs/{first}", headers=AUTH)
    assert first not in {j["id"] for j in client.get("/api/v1/maintenance", headers=AUTH).json()["jobs"]}


def test_due_states_done_and_snooze(client):
    client.get("/api/v1/maintenance", headers=AUTH)
    r = client.post("/api/v1/maintenance/jobs", headers=AUTH,
                    json={"title": "Clean the dryer lint trap", "room": "store", "every_days": 30, "last_done": "2026-09-20"})
    job = next(j for j in r.json()["jobs"] if j["title"] == "Clean the dryer lint trap")
    assert (job["state"], job["due_on"], job["days"]) == ("overdue", "2026-10-20", -9)
    assert r.json()["jobs"][0]["id"] == job["id"]  # overdue first
    assert r.json()["summary"]["rooms"] == ["store"]

    snoozed = next(j for j in client.post(f"/api/v1/maintenance/jobs/{job['id']}/snooze", headers=AUTH).json()["jobs"] if j["id"] == job["id"])
    assert (snoozed["state"], snoozed["due_on"]) == ("soon", "2026-11-05")
    done = next(j for j in client.post(f"/api/v1/maintenance/jobs/{job['id']}/done", headers=AUTH, json={}).json()["jobs"] if j["id"] == job["id"])
    assert (done["last_done"], done["due_on"], done["state"], done["snoozed_until"]) == ("2026-10-29", "2026-11-28", "ok", None)


def test_appliances_with_warranty_and_a_manual(client):
    r = client.post("/api/v1/maintenance/appliances", headers=AUTH, json={
        "name": "Office split system", "room": "office", "make": "Daikin", "model": "FTXM35", "bought_on": "2021-11-20",
        "warranty_until": "2026-11-20", "manual_url": "https://example.com/ftxm.pdf"})
    a = r.json()["appliances"][0]
    assert a["warranty_days"] == 22 and r.json()["summary"]["warranties_ending"] == [a["id"]]
    assert client.post("/api/v1/maintenance/appliances", headers=AUTH, json={"name": "x", "room": "office", "manual_url": "javascript:alert(1)"}).status_code == 422
    up = client.post(f"/api/v1/maintenance/appliances/{a['id']}/manual", headers=AUTH, files={"file": ("FTXM manual.pdf", b"%PDF-1.4", "application/pdf")})
    assert up.json()["appliances"][0]["manual"]["filename"] == "FTXM manual.pdf"
    assert client.get(f"/api/v1/maintenance/appliances/{a['id']}/manual", headers=AUTH).content == b"%PDF-1.4"
    assert client.post(f"/api/v1/maintenance/appliances/{a['id']}/manual", headers=AUTH, files={"file": ("x.exe", b"MZ", "x")}).status_code == 422
    client.delete(f"/api/v1/maintenance/appliances/{a['id']}", headers=AUTH)
    assert client.get("/api/v1/maintenance", headers=AUTH).json()["appliances"] == []


def test_notifications_once_with_buttons_that_work(client):
    doc = service.load()
    doc.jobs = [service.Job(id="j1", title="Clean the AC filters", room="office", every_days=90, last_done="2026-07-31")]
    doc.appliances = [service.Appliance(id="a1", name="Dishwasher", room="kitchen", warranty_until="2026-11-10")]
    service.save(doc)
    assert service.push_messages(datetime(2026, 10, 29, 8, 0)) == []  # before 9
    msgs = service.push_messages(datetime(2026, 10, 29, 9, 5))
    assert [m["key"] for m in msgs] == ["home:job:j1:2026-10-29", "home:warranty:a1:2026-11-10"]
    assert msgs[0]["topic"] == "home" and [a["id"] for a in msgs[0]["actions"]] == ["done", "snooze"]

    t = actions.sign(msgs[0]["target"], msgs[0]["actions"], msgs[0]["title"], msgs[0]["body"], msgs[0]["url"])
    r = client.post("/api/v1/push/act", json={"token": t, "action": "done"})
    assert r.status_code == 200 and r.json()["message"] == "Done. Next one in 90 days."
    assert service.load().jobs[0].last_done == "2026-10-29"


def test_existing_devices_get_the_home_topic_once(client, tmp_path):
    path = tmp_path / "subs.json"
    sub = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "x" * 20, "auth": "y" * 10}}
    path.write_text(json.dumps({"subscriptions": [{**sub, "topics": ["apps", "inbox", "brief", "career"]},
                                                  {**sub, "endpoint": "https://push.example/def", "topics": ["apps"]}]}))
    subs = push_store.subscriptions()
    assert subs[0].topics[-2:] == ["home", "nudges"] and subs[1].topics == ["apps"]  # and nudges after them (6.3)
    # Turned off later: stays off.
    push_store.upsert(subs[0].model_copy(update={"topics": ["apps", "inbox", "brief", "career"]}))
    assert "home" not in next(s for s in push_store.subscriptions() if s.endpoint.endswith("abc")).topics


def test_a_job_can_come_due_by_use(client):
    """6.2: the dryer's filter after 2 hours of running; the heat pump after 100 kWh."""
    from datetime import date

    r = client.post("/api/v1/maintenance/jobs", headers=AUTH, json={"title": "Clean the dryer filter", "room": "laundry",
                                                                     "usage_entity": "sensor.dryer_power", "usage_unit": "h", "usage_every": 2})
    assert r.status_code == 200, r.text
    client.post("/api/v1/maintenance/jobs", headers=AUTH, json={"title": "Service the heat pump", "room": "living", "every_days": 365,
                                                                "last_done": date.today().isoformat(), "usage_entity": "sensor.hp_energy",
                                                                "usage_unit": "kWh", "usage_every": 100})
    assert client.post("/api/v1/maintenance/jobs", headers=AUTH, json={"title": "Nothing", "room": "laundry"}).status_code == 422

    def sample(t, dryer_w, hp_kwh):
        service.sample_usage({"power": [{"entity_id": "sensor.dryer_power", "watts": dryer_w}],
                              "meters": [{"entity_id": "sensor.hp_energy", "kwh": hp_kwh}]}, t)

    sample(0, 2000, 500.0)
    for t in range(600, 600 * 13, 600):  # two hours of drying
        sample(t, 2000, 500.0 + t / 600)
    sample(600 * 13, 0, 590.0)  # stopped: doesn't count
    jobs = {j["title"]: j for j in client.get("/api/v1/maintenance", headers=AUTH).json()["jobs"]}
    dryer, hp = jobs["Clean the dryer filter"], jobs["Service the heat pump"]
    assert dryer["state"] == "due" and dryer["used"] == 2.0 and dryer["used_share"] == 100
    assert hp["state"] == "soon" and hp["used"] == 90.0  # 90 of 100 kWh, though the date is a year off
    msgs = service.push_messages(__import__("datetime").datetime.now().replace(hour=10))
    assert any("run 2 h since it was last done" in m["body"] for m in msgs)
    client.post(f"/api/v1/maintenance/jobs/{dryer['id']}/done", headers=AUTH, json={})
    again = {j["title"]: j for j in client.get("/api/v1/maintenance", headers=AUTH).json()["jobs"]}["Clean the dryer filter"]
    assert again["used"] == 0.0 and again["state"] == "ok"


def test_asking_the_manuals_finds_the_page_and_cites_it(client, monkeypatch):
    """6.4: the best pages by the question's words, answered by SirisAI from just those pages."""
    import httpx

    from app.hub import service as hub_service
    from app.hub.service import reset_hub
    from app.maintenance import manuals
    from tests.test_hub import ENV

    r = client.post("/api/v1/maintenance/appliances", headers=AUTH, json={"name": "Coffee machine", "room": "kitchen", "make": "Breville"})
    a = r.json()["appliances"][0]
    client.post(f"/api/v1/maintenance/appliances/{a['id']}/manual", headers=AUTH, files={"file": ("Barista.pdf", b"%PDF-1.4", "application/pdf")})
    stored = service.load().appliances[0].manual.stored
    (service.manuals_dir() / f"{stored}.pages.json").write_text(json.dumps([
        "Safety. Read all instructions.", "Descaling: fill the tank with descaling solution, press the clean button for 3 seconds.",
        "Cleaning the steam wand after each use."]))
    hits = manuals.search("how do I descale it?")
    assert hits[0]["page"] == 2 and hits[0]["appliance"] == "Coffee machine"
    asked: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/siris/ask":
            asked.append(json.loads(request.content)["prompt"])
            return httpx.Response(200, text="Fill the tank with descaler, then hold Clean for 3 seconds (p. 2).")
        return httpx.Response(404)

    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    reset_hub(ENV)
    body = client.post("/api/v1/maintenance/manuals/ask", headers=AUTH, json={"question": "How do I descale the coffee machine?"}).json()
    assert body["answer"].endswith("(p. 2).") and body["sources"][0]["page"] == 2
    assert "[Coffee machine, page 2]" in asked[0] and "Safety" not in asked[0]
    assert client.post("/api/v1/maintenance/manuals/ask", headers=AUTH, json={"question": "replace the timing belt"}).json()["sources"] == []
