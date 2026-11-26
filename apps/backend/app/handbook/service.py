"""The Server handbook (11.10): commands worth keeping. The built-in ones are in the web app (they hold nothing
private); yours, which may name your own hosts and paths, are kept here in handbook.json, not in the repo."""

from __future__ import annotations

import secrets
from typing import Any

from app.services import json_store

MAX = 300


def _path():
    return json_store.data_path("SIRISOS_HANDBOOK_PATH", "handbook.json")


def entries() -> list[dict[str, Any]]:
    raw = json_store.read(_path(), {})
    return list(raw.get("entries") or []) if isinstance(raw, dict) else []


def _save(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    json_store.write(_path(), {"entries": items[-MAX:]})
    return entries()


def add(cmd: str, what: str, section: str) -> list[dict[str, Any]]:
    return _save([*entries(), {"id": secrets.token_hex(6), "cmd": cmd.strip(), "what": what.strip(), "section": section.strip() or "Mine"}])


def change(entry_id: str, cmd: str | None, what: str | None, section: str | None) -> list[dict[str, Any]] | None:
    items = entries()
    found = next((e for e in items if e["id"] == entry_id), None)
    if found is None:
        return None
    for key, value in (("cmd", cmd), ("what", what), ("section", section)):
        if value is not None:
            found[key] = value.strip() or ("Mine" if key == "section" else found[key])
    return _save(items)


def remove(entry_id: str) -> list[dict[str, Any]] | None:
    items = entries()
    kept = [e for e in items if e["id"] != entry_id]
    return None if len(kept) == len(items) else _save(kept)
