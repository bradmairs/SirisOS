"""Push subscriptions (one per browser/device) and what's already been sent.

Each subscription picks its topics:
- apps:   a Siris app goes down
- inbox:  urgent and needs-attention inbox items (SirisAI alerts, approvals...)
- brief:  the daily brief is ready (once a morning)
- career: a career goal is due within a week, CPD hours about to drop out
- home:   a home job comes due, a warranty is ending, the network or power needs you (5.2)
- nudges: a free stretch when something's due, and winding down for bed (6.3)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from app.services import json_store

Topic = Literal["apps", "inbox", "brief", "career", "home", "nudges"]
TOPICS: tuple[str, ...] = ("apps", "inbox", "brief", "career", "home", "nudges")
# The topics before "home" (5.2): a device that had all of them gets it too.
_BEFORE_HOME = {"apps", "inbox", "brief", "career"}
MAX_SENT = 2000


class Keys(BaseModel):
    p256dh: str = Field(min_length=10, max_length=200)
    auth: str = Field(min_length=8, max_length=100)


class Subscription(BaseModel):
    endpoint: str = Field(min_length=10, max_length=2000, pattern=r"^https://")
    keys: Keys
    label: str = Field(default="", max_length=80)
    topics: list[Topic] = Field(default_factory=lambda: list(TOPICS))
    created_at: str = ""
    # 2 from 5.2 ("home"), 3 from 6.3 ("nudges"); older ones are upgraded on load.
    v: int = 3


def _subs_path():
    return json_store.data_path("SIRISOS_PUSH_SUBSCRIPTIONS_PATH", "push-subscriptions.json")


def _sent_path():
    return json_store.data_path("SIRISOS_PUSH_SENT_PATH", "push-sent.json")


def _health_path():
    return json_store.data_path("SIRISOS_PUSH_HEALTH_PATH", "push-health.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def health() -> dict[str, dict]:
    """Per device (endpoint): last_ok, last_error, last_error_at, failures in a row (6.0)."""
    return dict(json_store.read(_health_path(), {}))


def record(endpoint: str, error: str | None = None) -> None:
    """One delivery's outcome: a success clears the run of failures."""
    kept = health()
    h = dict(kept.get(endpoint) or {})
    if error is None:
        h.update(last_ok=_now(), failures=0)
    else:
        h.update(last_error=error[:300], last_error_at=_now(), failures=int(h.get("failures") or 0) + 1)
    kept[endpoint] = h
    json_store.write(_health_path(), kept)


def failing(sub: "Subscription", h: dict | None = None) -> bool:
    """Its last delivery failed (and nothing has got through since)."""
    h = h if h is not None else health().get(sub.endpoint) or {}
    return bool(h.get("failures")) and (h.get("last_error_at") or "") > (h.get("last_ok") or "")


def _upgrade(raw: dict) -> dict:
    if "v" not in raw:
        topics = list(raw.get("topics") or TOPICS)
        if _BEFORE_HOME <= set(topics) and "home" not in topics:
            topics.append("home")
        raw = {**raw, "topics": topics, "v": 2}
    if raw.get("v") == 2:
        # A device that had everything gets the new nudges too; one that picked gets to choose.
        topics = list(raw.get("topics") or [])
        if _BEFORE_HOME | {"home"} <= set(topics) and "nudges" not in topics:
            topics.append("nudges")
        raw = {**raw, "topics": topics, "v": 3}
    return raw


def subscriptions() -> list[Subscription]:
    return [Subscription.model_validate(_upgrade(s)) for s in json_store.read(_subs_path(), {}).get("subscriptions", [])]


def _save(subs: list[Subscription]) -> None:
    json_store.write(_subs_path(), {"subscriptions": [s.model_dump() for s in subs]})


def upsert(sub: Subscription) -> Subscription:
    subs = [s for s in subscriptions() if s.endpoint != sub.endpoint]
    old = next((s for s in subscriptions() if s.endpoint == sub.endpoint), None)
    sub.created_at = old.created_at if old else datetime.now(timezone.utc).isoformat(timespec="seconds")
    _save(subs + [sub])
    return sub


def remove(endpoint: str) -> bool:
    subs = subscriptions()
    kept = [s for s in subs if s.endpoint != endpoint]
    _save(kept)
    h = health()
    if h.pop(endpoint, None) is not None:
        json_store.write(_health_path(), h)
    return len(kept) != len(subs)


def sent() -> set[str]:
    return set(json_store.read(_sent_path(), {}).get("keys", []))


def mark_sent(keys: list[str]) -> None:
    if not keys:
        return
    existing = json_store.read(_sent_path(), {}).get("keys", [])
    merged = [k for k in existing if k not in keys] + keys
    json_store.write(_sent_path(), {"keys": merged[-MAX_SENT:]})
