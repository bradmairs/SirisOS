"""3.9: the access check's server side."""

from __future__ import annotations

import json
import socket

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.access import api as access
from app.entrypoint import app
from tests.test_hub import AUTH


@pytest.mark.parametrize("ip, network", [
    ("192.168.0.42", "home"), ("10.0.0.5", "home"), ("127.0.0.1", "home"), ("100.101.5.9", "vpn"),
    ("149.167.20.9", "internet"), ("::ffff:192.168.0.9", "home"), ("nonsense", "unknown"),
])
def test_networks(ip, network):
    assert access.network_of(ip) == network


def test_check_reports_where_from_and_terminal_hosts(monkeypatch):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    monkeypatch.setenv("SIRISOS_TERMINAL_HOSTS", f"home=brad@127.0.0.1:{port},gone=brad@127.0.0.1:1")
    try:
        body = TestClient(app).get("/api/v1/access", headers={**AUTH, "X-Forwarded-For": "149.167.20.9, 172.18.0.3"}).json()
    finally:
        listener.close()
    assert body["client_ip"] == "149.167.20.9" and body["network"] == "internet"
    assert [(h["name"], h["reachable"]) for h in body["terminal"]["hosts"]] == [("home", True), ("gone", False)]
    assert body["certificate"] is None  # plain http here


def test_needs_sign_in():
    assert TestClient(app).get("/api/v1/access").status_code == 401


def test_stream_sends_two_events_apart():
    with TestClient(app).stream("GET", "/api/v1/access/stream?gap=0.2", headers=AUTH) as r:
        events = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
    assert [e["n"] for e in events] == [1, 2] and events[1]["at"] - events[0]["at"] >= 0.19


def test_websocket_probe_needs_same_origin():
    client = TestClient(app, base_url="http://testserver")
    with client.websocket_connect("/api/v1/terminal/ws?probe=1", headers={"Origin": "http://testserver"}) as ws:
        assert json.loads(ws.receive_text()) == {"type": "probe"}
    with pytest.raises(WebSocketDisconnect) as exc:
        with TestClient(app).websocket_connect("/api/v1/terminal/ws?probe=1", headers={"Origin": "https://evil.example"}):
            pass
    assert exc.value.code == 4403
