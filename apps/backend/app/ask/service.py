"""Ask Siris from anywhere (11.16): an iPhone Shortcut (the Action Button, or "Hey Siri, Ask Siris") sends what you
said, SirisAI answers, and the Shortcut speaks the answer.

A Shortcut can't keep a SirisOS sign-in, so it uses a key made on the Security page: shown once, kept only as its
SHA-256, replaced by a new one or turned off there. Unlike the Add to SirisOS key, this one can read: it asks
SirisAI anything you could ask in the app, and SirisAI can do everyday things (lights, a timer). It can never
approve anything: whatever needs your OK is left for you in the app. At most LIMIT_PER_HOUR questions an hour.

Follow-ups work: a question within FOLLOW_UP_SECONDS of the last answer carries on the same conversation.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from collections import deque
from typing import Any

from app.services import json_store

LIMIT_PER_HOUR = 60
FOLLOW_UP_SECONDS = 10 * 60
MAX_CHARS = 2000
_lock = threading.Lock()
_recent: deque[float] = deque()
_last: dict[str, Any] = {}


def _path():
    return json_store.data_path("SIRISOS_ASK_PATH", "ask.json")


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def new_key() -> str:
    key = "sa_" + secrets.token_urlsafe(24)
    json_store.write(_path(), {"key_hash": _digest(key), "made": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    _last.clear()
    return key


def drop_key() -> None:
    json_store.write(_path(), {})
    _last.clear()


def state() -> dict[str, Any]:
    doc = json_store.read(_path(), {})
    return {"on": bool(doc.get("key_hash")), "made": doc.get("made")}


def matches(key: str | None) -> bool:
    stored = json_store.read(_path(), {}).get("key_hash") or ""
    return bool(key and stored) and hmac.compare_digest(_digest(key), stored)


def allow() -> bool:
    now = time.monotonic()
    with _lock:
        while _recent and now - _recent[0] > 3600:
            _recent.popleft()
        if len(_recent) >= LIMIT_PER_HOUR:
            return False
        _recent.append(now)
        return True


def conversation(explicit: str | None, now: float | None = None) -> str | None:
    """The conversation to carry on: the one asked for, else the last one if it was recent."""
    if explicit:
        return explicit
    now = time.monotonic() if now is None else now
    if _last.get("id") and now - float(_last.get("at") or 0) < FOLLOW_UP_SECONDS:
        return str(_last["id"])
    return None


def remember(conversation_id: str | None, now: float | None = None) -> None:
    if conversation_id:
        _last.update(id=conversation_id, at=time.monotonic() if now is None else now)


def say(out: dict[str, Any]) -> str:
    """What the Shortcut speaks."""
    if out.get("confirmation_required"):
        return "That needs your OK. I've left it in SirisOS for you to confirm."
    text = str(out.get("response") or "").strip()
    if text:
        return text
    if out.get("error"):
        return f"SirisAI couldn't answer that: {str(out['error'])[:200]}"
    return "Done."
