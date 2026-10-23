"""Terminal shortcuts (3.4): one-tap commands, each run behind its own fresh
2FA code like a terminal session.

A shortcut is a name and a command line, optionally pinned to one host. It
runs non-interactively over SSH (no terminal), for up to
SIRISOS_TERMINAL_COMMAND_SECONDS (60); its output (stdout and stderr, the
last 64 KB) comes back to the page. Running one is logged, like a session.

Three read-only ones are built in; the rest are yours, kept in terminal.json.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from app.terminal import store

BUILT_IN = [
    {"id": "builtin:containers", "name": "What's running", "command": "docker ps --format 'table {{.Names}}\\t{{.Status}}'", "host": None, "builtin": True},
    {"id": "builtin:disk", "name": "Disk space", "command": "df -h -x tmpfs -x devtmpfs -x squashfs -x overlay", "host": None, "builtin": True},
    {"id": "builtin:memory", "name": "Memory and load", "command": "free -h && uptime", "host": None, "builtin": True},
]
MAX_OUTPUT = 64 * 1024
MAX_SAVED = 40


def seconds() -> int:
    try:
        return max(5, min(600, int(os.getenv("SIRISOS_TERMINAL_COMMAND_SECONDS", "60"))))
    except ValueError:
        return 60


def saved() -> list[dict[str, Any]]:
    return [{**c, "builtin": False} for c in store.load().get("commands") or []]


def all_commands() -> list[dict[str, Any]]:
    return BUILT_IN + saved()


def find(command_id: str) -> dict[str, Any] | None:
    return next((c for c in all_commands() if c["id"] == command_id), None)


def add(name: str, command: str, host: str | None) -> dict[str, Any]:
    state = store.load()
    items = state.get("commands") or []
    if len(items) >= MAX_SAVED:
        raise ValueError(f"Up to {MAX_SAVED} shortcuts.")
    item = {"id": uuid.uuid4().hex[:10], "name": name.strip(), "command": command.strip(), "host": host or None, "created_at": store.now()}
    state["commands"] = items + [item]
    store.save(state)
    return {**item, "builtin": False}


def remove(command_id: str) -> bool:
    state = store.load()
    items = state.get("commands") or []
    kept = [c for c in items if c["id"] != command_id]
    state["commands"] = kept
    store.save(state)
    return len(kept) != len(items)


def tail(text: str) -> tuple[str, bool]:
    data = text.encode("utf-8", errors="replace")
    if len(data) <= MAX_OUTPUT:
        return text, False
    return data[-MAX_OUTPUT:].decode("utf-8", errors="ignore"), True
