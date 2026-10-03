"""Links (the Homarr replacement): store, API, status checks and the Homarr importer."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.hub import service
from app.links import api as links_api
from app.links import import_homarr

PNG = b"\x89PNG\r\n\x1a\nfake"


def _auth() -> dict[str, str]:
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": "brad", "iat": now, "exp": now + timedelta(hours=1), "iss": "sirisos-api"},
                       "change-this-development-secret", algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SIRISOS_LINKS_PATH", str(tmp_path / "links.json"))
    links_api._status_cache.clear()
    return TestClient(app)


DOC = {"groups": [{"name": "Media", "links": [
    {"id": "plex", "name": "Plex", "url": "http://plex.local:32400", "icon": "https://cdn/plex.png", "note": "LAN"},
    {"id": "gone", "name": "Old app", "url": "http://gone.local:1234"},
]}]}


def test_links_need_sign_in(client):
    assert client.get("/api/v1/links").status_code == 401


def test_save_and_read_links(client, tmp_path):
    assert client.get("/api/v1/links", headers=_auth()).json()["groups"] == []
    saved = client.put("/api/v1/links", headers=_auth(), json=DOC).json()
    assert saved["updated_at"]
    assert client.get("/api/v1/links", headers=_auth()).json()["groups"][0]["links"][0]["name"] == "Plex"
    assert json.loads((tmp_path / "links.json").read_text())["groups"][0]["name"] == "Media"


def test_rejects_non_web_links(client):
    bad = {"groups": [{"name": "X", "links": [{"name": "Bad", "url": "javascript:alert(1)"}]}]}
    assert client.put("/api/v1/links", headers=_auth(), json=bad).status_code == 422


def test_status_treats_any_answer_as_up(client, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "gone.local":
            raise httpx.ConnectError("refused")
        return httpx.Response(401)  # a login wall still means the app is up

    monkeypatch.setattr(service, "transport", httpx.MockTransport(handler))
    client.put("/api/v1/links", headers=_auth(), json=DOC)
    status = client.get("/api/v1/links/status", headers=_auth()).json()
    assert status["plex"]["up"] is True and status["plex"]["status"] == 401
    assert status["gone"] == {"up": False, "status": None, "ms": None, "error": "ConnectError"}


def _homarr_db(path) -> str:
    db = sqlite3.connect(path)
    db.executescript("""
        create table app (id text, name text, description text, icon_url text, href text, ping_url text);
        create table media (id text, name text, content blob, content_type text, size int, created_at int, creator_id text);
        create table board (id text, name text);
        create table item (id text, board_id text, kind text, options text, advanced_options text);
        create table item_layout (item_id text, section_id text, layout_id text, x_offset int, y_offset int, width int, height int);
    """)
    db.executemany("insert into app values (?,?,?,?,?,?)", [
        ("a1", "Radarr", None, "https://cdn/radarr.svg", "http://10.0.0.5:7878/", None),
        ("a2", "Radarr", None, "https://cdn/radarr.png", "http://10.0.0.5:7878", None),
        ("a3", "Tool", None, "/api/user-medias/m1", "https://tool.example.com", None),
        ("a4", "Wiki", None, "https://cdn/obsidian.svg", "https://wiki.example.com", None),
        ("a5", "Self", None, None, "http://10.0.0.5:6464", None),
    ])
    db.execute("insert into media values ('m1', 'icon.png', ?, 'image/png', 4, 0, 'u')", (PNG,))
    db.executemany("insert into board values (?,?)", [("b1", "Main"), ("b2", "Work")])
    db.executemany("insert into item values (?,?,?,?,?)", [
        ("i1", "b1", "app", json.dumps({"json": {"appId": "a1"}}), None),
        ("i2", "b2", "app", json.dumps({"json": {"appId": "a4"}}), None),
        ("i3", "b1", "downloads", "{}", None),
    ])
    db.executemany("insert into item_layout values (?,?,?,?,?,?,?)",
                   [("i1", "s", "l", 0, 0, 1, 1), ("i2", "s", "l", 0, 0, 1, 1), ("i3", "s", "l", 1, 0, 1, 1)])
    db.commit()
    return str(path)


def test_import_homarr(tmp_path, monkeypatch):
    monkeypatch.setenv("SIRISOS_LINKS_PATH", str(tmp_path / "links.json"))
    doc, report = import_homarr.run(_homarr_db(tmp_path / "db.sqlite"), {"Work"}, {"Self"})
    groups = {g.name: g.links for g in doc.groups}
    assert [l.name for l in groups["Downloads"]] == ["Radarr"]  # duplicate address merged
    assert [l.name for l in groups["Work"]] == ["Wiki"]  # on the Work board
    tool = groups["Other"][0]
    assert tool.icon == "data:image/png;base64," + __import__("base64").b64encode(PNG).decode()
    assert groups["Downloads"][0].note == "LAN" and tool.note == "Remote"
    assert "Self" in report["skipped"]
    assert report["widgets_not_imported"] == ["Main: downloads"]

    assert import_homarr.main([str(tmp_path / "db.sqlite"), "--board-groups", "Work"]) == 0
    assert json.loads((tmp_path / "links.json").read_text())["groups"]
