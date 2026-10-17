"""Push subscriptions (one per browser/device) and what's already been sent.

Each subscription picks its topics:
- apps:   a Siris app goes down
- inbox:  urgent and needs-attention inbox items (SirisAI alerts, approvals...)
- brief:  the daily brief is ready (once a morning)
- career: a career goal is due within a week, CPD hours about to drop out
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from app.services import json_store

Topic = Literal["apps", "inbox", "brief", "career"]
TOPICS: tuple[str, ...] = ("apps", "inbox", "brief", "career")
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


def _subs_path():
    return json_store.data_path("SIRISOS_PUSH_SUBSCRIPTIONS_PATH", "push-subscriptions.json")


def _sent_path():
    return json_store.data_path("SIRISOS_PUSH_SENT_PATH", "push-sent.json")


def subscriptions() -> list[Subscription]:
    return [Subscription.model_validate(s) for s in json_store.read(_subs_path(), {}).get("subscriptions", [])]


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
    return len(kept) != len(subs)


def sent() -> set[str]:
    return set(json_store.read(_sent_path(), {}).get("keys", []))


def mark_sent(keys: list[str]) -> None:
    if not keys:
        return
    existing = json_store.read(_sent_path(), {}).get("keys", [])
    merged = [k for k in existing if k not in keys] + keys
    json_store.write(_sent_path(), {"keys": merged[-MAX_SENT:]})
