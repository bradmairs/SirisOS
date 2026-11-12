"""Add to SirisOS from anywhere (8.9): the iPhone Share Sheet or a Shortcut sends a photo, PDF, link or text, and
it lands in the right place.

- **A file** (a photo or PDF) goes to SirisAI's documents (Life admin), which reads it: a receipt is kept with its
  things added to Things you own, a bill gets its due date, a letter is filed.
- **A link** is saved to Siris, which reads the page.
- **Text** that reads like a to-do ("remind me to…", "todo …", "buy milk tomorrow" sent as a task) becomes a task,
  due today unless it says when; anything else is a note in Siris.

The Shortcut signs in with a key made on the Security page, shown once and kept only as its SHA-256. The key can
only add these things: it can't read, change or delete anything. A new key replaces the old one.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import threading
import time
from collections import deque
from typing import Any

from app.services import json_store

LIMIT_PER_HOUR = 120
URL = re.compile(r"^\s*(https?://\S+)\s*$", re.I)
TODO = re.compile(r"^\s*(?:todo|to do|task|remind me)\b", re.I)
LEAD = re.compile(r"^\s*(?:todo|to do|task)\b\s*[:-]?\s*", re.I)  # taken off; "remind me to…" is left for the task parser
_lock = threading.Lock()
_recent: deque[float] = deque()


def _path():
    return json_store.data_path("SIRISOS_SHARE_PATH", "share.json")


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def new_key() -> str:
    key = "so_" + secrets.token_urlsafe(24)
    json_store.write(_path(), {"key_hash": _digest(key), "made": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    return key


def drop_key() -> None:
    json_store.write(_path(), {})


def state() -> dict[str, Any]:
    doc = json_store.read(_path(), {})
    return {"on": bool(doc.get("key_hash")), "made": doc.get("made")}


def matches(key: str | None) -> bool:
    stored = json_store.read(_path(), {}).get("key_hash") or ""
    return bool(key and stored) and hmac.compare_digest(_digest(key), stored)


def allow() -> bool:
    """At most LIMIT_PER_HOUR adds an hour, so a leaked key can't flood anything."""
    now = time.monotonic()
    with _lock:
        while _recent and now - _recent[0] > 3600:
            _recent.popleft()
        if len(_recent) >= LIMIT_PER_HOUR:
            return False
        _recent.append(now)
        return True


def kind_of(text: str, as_task: bool = False) -> str:
    """'url', 'task' or 'note' for shared text."""
    if URL.match(text):
        return "url"
    return "task" if as_task or TODO.match(text) else "note"
