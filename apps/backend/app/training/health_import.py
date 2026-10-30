"""Apple Health into SirisOS on its own (5.5).

Apple Health has no server API: the data has to leave the phone. Two ways,
both posting to one SirisOS address with a key made here:

- **Health Auto Export** (an iPhone app): an automation of type "REST API"
  posts Health data as JSON every hour or so in the background. SirisAI
  3.11 reads its format.
- **An iPhone Shortcut** on a daily personal automation: "Find Health
  Samples" for each metric, then "Get Contents of URL" with
  {"date": ..., "metrics": {"steps": ..., "sleep_hours": ...}}.

POST /api/v1/health/import with `Authorization: Bearer <key>` (or
`X-Health-Key: <key>`). SirisOS passes the body to SirisAI's
/siris/health/metrics, so it's stored where the brief, Your year, fitness
and training already read it. Only a hash of the key is kept; making a new
one stops the old one.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import Any

from app.services import json_store

MAX_BYTES = 10 * 1024 * 1024


def _path():
    return json_store.data_path("SIRISOS_HEALTH_IMPORT_PATH", "health-import.json")


def _load() -> dict[str, Any]:
    doc = json_store.read(_path(), {})
    return doc if isinstance(doc, dict) else {}


def _hash(key: str) -> str:
    return hashlib.sha256(f"sirisos-health:{key}".encode()).hexdigest()


def new_key() -> str:
    key = "hk_" + secrets.token_urlsafe(30)
    doc = _load()
    doc.update(key_hash=_hash(key), key_hint=key[-4:], made=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    json_store.write(_path(), doc)
    return key


def check(presented: str | None) -> bool:
    stored = _load().get("key_hash")
    return bool(presented and stored and hmac.compare_digest(_hash(presented.strip()), stored))


def note(result: dict[str, Any] | None, error: str | None = None) -> None:
    doc = _load()
    entry: dict[str, Any] = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if error:
        entry["error"] = error[:300]
    else:
        days = (result or {}).get("days")
        entry["days"] = sorted(days)[-14:] if isinstance(days, dict) else [(result or {}).get("date")]
        entry["format"] = (result or {}).get("format") or "metrics"
    doc["last"] = entry
    if not error:
        doc["last_ok"] = entry
    json_store.write(_path(), doc)


def status() -> dict[str, Any]:
    doc = _load()
    return {"has_key": bool(doc.get("key_hash")), "key_hint": doc.get("key_hint"), "made": doc.get("made"),
            "last": doc.get("last"), "last_ok": doc.get("last_ok")}
