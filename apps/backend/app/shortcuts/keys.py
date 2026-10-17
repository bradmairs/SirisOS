"""Shortcut keys: long-lived keys for Apple Shortcuts (and Siri), which
can't sign in. Each key starts "sk_", is shown once, and only its SHA-256
is kept. A key opens only the /api/v1/shortcuts actions it was given:
capture, ask, today, protocols. Revoke one and it stops working at once.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import Header, HTTPException
from pydantic import BaseModel, Field

from app.services import json_store

Scope = Literal["capture", "ask", "today", "protocols"]
SCOPES: tuple[str, ...] = ("capture", "ask", "today", "protocols")
PREFIX = "sk_"


class Key(BaseModel):
    id: str
    label: str
    hash: str
    scopes: list[Scope]
    created_at: str
    last_used: str | None = None


def _path():
    return json_store.data_path("SIRISOS_SHORTCUT_KEYS_PATH", "shortcut-keys.json")


def _digest(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load() -> list[Key]:
    return [Key.model_validate(k) for k in json_store.read(_path(), {}).get("keys", [])]


def _save(keys: list[Key]) -> None:
    json_store.write(_path(), {"keys": [k.model_dump() for k in keys]})


def public(key: Key) -> dict:
    return {"id": key.id, "label": key.label, "scopes": key.scopes, "created_at": key.created_at, "last_used": key.last_used}


def create(label: str, scopes: list[str]) -> tuple[Key, str]:
    secret = PREFIX + secrets.token_urlsafe(32)
    key = Key(id=uuid.uuid4().hex[:10], label=label.strip() or "Shortcut", hash=_digest(secret),
              scopes=[s for s in SCOPES if s in scopes] or ["capture"], created_at=_now())
    _save(load() + [key])
    return key, secret


def revoke(key_id: str) -> bool:
    keys = load()
    kept = [k for k in keys if k.id != key_id]
    _save(kept)
    return len(kept) != len(keys)


def check(secret: str, scope: str) -> Key:
    digest = _digest(secret)
    keys = load()
    for key in keys:
        if hmac.compare_digest(key.hash, digest):
            if scope not in key.scopes:
                raise HTTPException(status_code=403, detail=f"This shortcut key can't {scope}. Give it that in SirisOS → iPhone shortcuts.")
            key.last_used = _now()
            _save(keys)
            return key
    raise HTTPException(status_code=401, detail="Unknown or revoked shortcut key.")


def requires(scope: str):
    """A route dependency: the request carries a shortcut key allowed to do `scope`."""

    def dependency(authorization: str | None = Header(None), x_shortcut_key: str | None = Header(None)) -> Key:
        secret = (x_shortcut_key or "").strip() or (authorization[7:].strip() if authorization and authorization.startswith("Bearer ") else "")
        if not secret.startswith(PREFIX):
            raise HTTPException(status_code=401, detail="Send a shortcut key: Authorization: Bearer sk_…")
        return check(secret, scope)

    return dependency


class NewKey(BaseModel):
    label: str = Field(default="", max_length=60)
    scopes: list[Scope] = Field(default_factory=lambda: ["capture", "ask", "today"])
