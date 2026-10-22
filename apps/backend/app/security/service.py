"""Passkeys, single-use challenges, sign-in rate limiting and the settings check."""

from __future__ import annotations

import os
import secrets
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from app.services import json_store

CHALLENGE_SECONDS = 300
# Sign-in attempts: this many failures per client within the window, then 429.
MAX_FAILURES = 8
FAILURE_WINDOW = 15 * 60


class Passkey(BaseModel):
    id: str  # credential id, base64url
    label: str
    public_key: str  # DER SubjectPublicKeyInfo, base64url
    alg: int
    sign_count: int = 0
    rp_id: str
    created_at: str
    last_used: str | None = None


def _path():
    return json_store.data_path("SIRISOS_PASSKEYS_PATH", "passkeys.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def passkeys() -> list[Passkey]:
    return [Passkey.model_validate(p) for p in json_store.read(_path(), {}).get("passkeys", [])]


def save_passkeys(items: list[Passkey]) -> None:
    json_store.write(_path(), {"passkeys": [p.model_dump() for p in items]})


def add_passkey(item: Passkey) -> None:
    save_passkeys([p for p in passkeys() if p.id != item.id] + [item])


def remove_passkey(cred_id: str) -> bool:
    items = passkeys()
    kept = [p for p in items if p.id != cred_id]
    save_passkeys(kept)
    return len(kept) != len(items)


def public(p: Passkey) -> dict[str, Any]:
    return {"id": p.id, "label": p.label, "rp_id": p.rp_id, "created_at": p.created_at, "last_used": p.last_used}


# -- challenges: single use, five minutes ---------------------------------------

_challenges: dict[str, tuple[str, str, float]] = {}  # challenge -> (purpose, rp_id, expires)
_lock = threading.Lock()


def new_challenge(purpose: str, rp_id: str) -> str:
    challenge = secrets.token_urlsafe(32)
    now = time.monotonic()
    with _lock:
        for k in [k for k, v in _challenges.items() if v[2] < now]:
            _challenges.pop(k, None)
        _challenges[challenge] = (purpose, rp_id, now + CHALLENGE_SECONDS)
    return challenge


def take_challenge(challenge: str, purpose: str) -> str | None:
    """The challenge's rp_id if it's live and for this purpose; it can't be used twice."""
    with _lock:
        found = _challenges.pop(challenge, None)
    if not found or found[0] != purpose or found[2] < time.monotonic():
        return None
    return found[1]


# -- sign-in rate limiting ------------------------------------------------------

_failures: dict[str, deque[float]] = {}


def blocked_for(client: str) -> int:
    """Seconds until this client may try again (0 = now)."""
    now = time.monotonic()
    with _lock:
        recent = _failures.get(client)
        if not recent:
            return 0
        while recent and recent[0] < now - FAILURE_WINDOW:
            recent.popleft()
        return int(recent[0] + FAILURE_WINDOW - now) + 1 if len(recent) >= MAX_FAILURES else 0


def failed(client: str) -> None:
    with _lock:
        _failures.setdefault(client, deque()).append(time.monotonic())


def succeeded(client: str) -> None:
    with _lock:
        _failures.pop(client, None)


def reset() -> None:
    with _lock:
        _failures.clear()
        _challenges.clear()


# -- the settings check -----------------------------------------------------------

def checks() -> list[dict[str, str]]:
    """What a security review of this install finds, worst first."""
    out: list[dict[str, str]] = []
    jwt_secret = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")
    password = os.getenv("SIRISOS_ADMIN_PASSWORD", "change-me")
    if jwt_secret in ("change-this-development-secret", "replace-with-a-long-random-secret") or len(jwt_secret) < 32:
        out.append({"level": "critical", "title": "Sign-in secret is a default or too short",
                    "fix": "Set SIRISOS_JWT_SECRET to a long random value (openssl rand -hex 32) and restart. Everyone signs in again."})
    if password in ("change-me", "change-this-password") or len(password) < 12:
        out.append({"level": "critical", "title": "Admin password is a default or shorter than 12 characters",
                    "fix": "Set a longer SIRISOS_ADMIN_PASSWORD, or add a passkey and use that."})
    key = os.getenv("SIRISOS_SERVICE_KEY", "").strip()
    if key and len(key) < 24:
        out.append({"level": "warning", "title": "SirisAI's service key is too short and is being ignored",
                    "fix": "Use at least 24 characters for SIRISOS_SERVICE_KEY (and SIRISAI_SIRISOS_SERVICE_KEY in SirisAI)."})
    if os.getenv("SIRISOS_HUB_VERIFY_SSL", "true").lower() in ("0", "false", "no"):
        out.append({"level": "info", "title": "HTTPS certificates of the other apps aren't checked",
                    "fix": "Fine on your own network with self-signed certificates; turn SIRISOS_HUB_VERIFY_SSL back on if they get real ones."})
    hours = int(os.getenv("SIRISOS_JWT_EXPIRY_HOURS", "24") or 24)
    if hours > 24 * 7:
        out.append({"level": "warning", "title": f"Sessions last {hours} hours",
                    "fix": "A week or less (SIRISOS_JWT_EXPIRY_HOURS) limits what a lost phone can do."})
    from app.terminal import service as terminal

    if terminal.enabled():
        names = ", ".join(h.name for h in terminal.hosts())
        if not terminal.two_factor()["set_up"]:
            out.append({"level": "warning", "title": f"The terminal is on ({names}) but 2FA isn't set up",
                        "fix": "It can't open until it is: set up 2FA on the Terminal page, or clear SIRISOS_TERMINAL_HOSTS."})
        else:
            out.append({"level": "info", "title": f"The terminal can open a shell on {names}",
                        "fix": "Each session needs a fresh 2FA code. Reach SirisOS over Tailscale or a VPN, never a port forward."})
    if not passkeys():
        out.append({"level": "info", "title": "No passkey yet",
                    "fix": "Add one below to sign in with Face ID instead of the password."})
    return out


def new_id() -> str:
    return uuid.uuid4().hex
