"""9.5: with the code public, its development secret and password must never work on a real install."""

import jwt
from fastapi.testclient import TestClient

from app import secrets_config
from app.entrypoint import app


def _fresh(monkeypatch, tmp_path, **env):
    monkeypatch.setenv("SIRISOS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("SIRISOS_ALLOW_DEV_SECRETS", raising=False)
    for k in ("SIRISOS_JWT_SECRET", "SIRISOS_ADMIN_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(secrets_config, "_cached", None)


def test_a_missing_or_published_secret_is_never_used(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path)
    made = secrets_config.jwt_secret()
    assert made != secrets_config.DEV_SECRET and len(made) == 64
    assert (tmp_path / "jwt-secret").read_text() == made and (tmp_path / "jwt-secret").stat().st_mode & 0o077 == 0
    monkeypatch.setattr(secrets_config, "_cached", None)
    assert secrets_config.jwt_secret() == made  # kept across restarts

    forged = jwt.encode({"sub": "brad", "iss": "sirisos-api", "exp": 9999999999}, secrets_config.DEV_SECRET, algorithm="HS256")
    assert TestClient(app).get("/api/v1/tasks", headers={"Authorization": f"Bearer {forged}"}).status_code == 401

    _fresh(monkeypatch, tmp_path, SIRISOS_JWT_SECRET="replace-with-a-long-random-secret")
    assert secrets_config.jwt_secret() == made
    strong = "x" * 40
    _fresh(monkeypatch, tmp_path, SIRISOS_JWT_SECRET=strong)
    assert secrets_config.jwt_secret() == strong


def test_a_missing_or_published_password_never_signs_in(monkeypatch, tmp_path):
    for pw in ("", "change-me", "change-this-password"):
        _fresh(monkeypatch, tmp_path, **({"SIRISOS_ADMIN_PASSWORD": pw} if pw else {}))
        r = TestClient(app).post("/api/v1/auth/login", json={"username": "brad", "password": pw or "change-me"}, headers={"X-Forwarded-For": f"10.9.0.{len(pw)}"})
        assert r.status_code == 403 and "SIRISOS_ADMIN_PASSWORD" in r.json()["detail"]
    _fresh(monkeypatch, tmp_path, SIRISOS_ADMIN_PASSWORD="a-real-password-123")
    r = TestClient(app).post("/api/v1/auth/login", json={"username": "brad", "password": "a-real-password-123"}, headers={"X-Forwarded-For": "10.9.1.1"})
    assert r.status_code == 200
