"""Home layout: per-device widget order and hidden widgets."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app


def _auth() -> dict[str, str]:
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": "brad", "iat": now, "exp": now + timedelta(hours=1), "iss": "sirisos-api"},
                       "change-this-development-secret", algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SIRISOS_HOME_LAYOUT_PATH", str(tmp_path / "home-layout.json"))
    return TestClient(app)


def test_layout_starts_empty_and_needs_sign_in(client):
    assert client.get("/api/v1/home/layout").status_code == 401
    body = client.get("/api/v1/home/layout", headers=_auth()).json()
    assert body["phone"] == {"order": [], "hidden": []}
    assert body["desktop"] == {"order": [], "hidden": []}


def test_layout_is_saved_per_device_and_cleaned(client, tmp_path):
    put = client.put("/api/v1/home/layout", headers=_auth(), json={
        "phone": {"order": ["weather", "clock", "weather", " "], "hidden": ["server"]},
        "desktop": {"order": ["app:reviewer"]},
    })
    assert put.status_code == 200
    assert put.json()["phone"] == {"order": ["weather", "clock"], "hidden": ["server"]}
    assert put.json()["updated_at"]
    again = client.get("/api/v1/home/layout", headers=_auth()).json()
    assert again["desktop"] == {"order": ["app:reviewer"], "hidden": []}
    assert (tmp_path / "home-layout.json").exists()
