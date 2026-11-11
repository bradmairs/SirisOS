"""8.5: the Home Lab diagram, from the network watch, the terminal's machines and SirisAI's Docker."""

from fastapi.testclient import TestClient

from app.entrypoint import app
from app.homelab import service
from tests.test_hub import AUTH


def test_the_diagram_guesses_what_plugs_into_what_and_keeps_your_changes(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_HOMELAB_PATH", str(tmp_path / "homelab.json"))
    monkeypatch.setenv("SIRISOS_TERMINAL_HOSTS", "unraid=root@192.168.0.100")
    monkeypatch.setattr(service, "_network", lambda: [
        {"id": "gw", "name": "UDM Pro", "kind": "gateway", "online": True, "important": True},
        {"id": "sw", "name": "USW 24", "kind": "switch", "online": True, "important": True},
        {"id": "ap", "name": "U6 Lite", "kind": "access_point", "online": False, "important": True},
        {"id": "tv", "name": "Lounge TV", "kind": "client", "online": True, "important": False},
        {"id": "hue", "name": "Hue Bridge", "kind": "client", "online": True, "important": True, "room": "Lounge"}])

    async def containers(hub):
        return [{"name": "plex", "state": "running"}, {"name": "open-webui", "state": "exited"}]

    monkeypatch.setattr(service, "_containers", containers)
    client = TestClient(app)
    d = client.get("/api/v1/homelab", headers=AUTH).json()
    by = {n["id"]: n for n in d["nodes"]}
    assert by["net:gw"]["parent"] == "internet" and by["net:sw"]["parent"] == "net:gw" and by["net:ap"]["parent"] == "net:sw"
    assert by["server:unraid"]["parent"] == "net:sw" and by["server:unraid"]["detail"] == "192.168.0.100"
    assert by["docker"]["parent"] == "server:unraid" and by["docker"]["detail"] == "1 of 2 containers running"
    assert by["net:hue"]["kind"] == "device" and by["net:hue"]["detail"] == "Lounge"
    assert "net:tv" not in by and d["clients"] == {"total": 1, "online": 1}

    added = client.post("/api/v1/homelab", headers=AUTH, json={"label": "NBN modem", "kind": "modem"}).json()
    modem = next(n for n in added["nodes"] if n["label"] == "NBN modem")
    assert next(n for n in added["nodes"] if n["id"] == "net:gw")["parent"] == modem["id"]  # the gateway now goes through the modem
    moved = client.patch("/api/v1/homelab/net:ap", headers=AUTH, json={"parent": "net:gw", "model": "U6 Lite", "notes": "Hallway ceiling"}).json()
    ap = next(n for n in moved["nodes"] if n["id"] == "net:ap")
    assert ap["parent"] == "net:gw" and ap["parent_guessed"] is False and ap["notes"] == "Hallway ceiling"
    # A loop (the gateway under the access point under the gateway) falls back to the internet.
    looped = client.patch("/api/v1/homelab/net:gw", headers=AUTH, json={"parent": "net:ap"}).json()
    assert next(n for n in looped["nodes"] if n["id"] == "net:gw")["parent"] == "internet"
    assert client.delete("/api/v1/homelab/net:gw", headers=AUTH).status_code == 404
    gone = client.delete(f"/api/v1/homelab/{modem['id']}", headers=AUTH).json()
    assert all(n["label"] != "NBN modem" for n in gone["nodes"])
