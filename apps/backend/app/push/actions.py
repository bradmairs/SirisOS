"""Buttons on phone notifications (3.8): Done, In an hour, Snooze, Approve...

The service worker that shows a notification can't sign in, so each
actionable notification carries a signed token naming the one thing it may
act on (a task or an inbox item) and the buttons it may press. A token works
once and runs out after two days. The push payload is end-to-end encrypted
to the device, so only that phone ever sees it.

iPhone notifications have no buttons, so tapping an actionable one opens
`/act?t=<token>`: the same buttons, full screen, before signing in.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timedelta
from typing import Any

from app.services import json_store

TTL_SECONDS = 48 * 3600
MAX_USED = 1000

TITLES = {"done": "Done", "later": "In an hour", "snooze": "Snooze 3 h", "dismiss": "Dismiss"}


class BadToken(Exception):
    pass


def _key() -> bytes:
    secret = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")
    return hashlib.sha256(f"sirisos-push-actions:{secret}".encode()).digest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign(target: str, actions: list[dict[str, str]], title: str, body: str, url: str, now: float | None = None) -> str:
    """`actions` are [{id, title}]; `target` is task:<id> or inbox:<id>."""
    payload = {"t": target, "a": actions, "ti": title[:200], "b": body[:300], "u": url,
               "e": int((now or time.time()) + TTL_SECONDS), "n": secrets.token_urlsafe(9)}
    raw = _b64(json.dumps(payload, separators=(",", ":")).encode())
    return f"{raw}.{_b64(hmac.new(_key(), raw.encode(), hashlib.sha256).digest()[:24])}"


def verify(token: str, now: float | None = None) -> dict[str, Any]:
    raw, _, mac = token.partition(".")
    try:
        good = hmac.compare_digest(_unb64(mac), hmac.new(_key(), raw.encode(), hashlib.sha256).digest()[:24])
        payload = json.loads(_unb64(raw)) if good else None
    except (ValueError, TypeError):
        payload = None
    if not isinstance(payload, dict):
        raise BadToken("This notification's buttons aren't valid.")
    if payload.get("e", 0) < (now or time.time()):
        raise BadToken("This notification is more than two days old. Open SirisOS to act on it.")
    return payload


def _used_path():
    return json_store.data_path("SIRISOS_PUSH_ACTIONS_PATH", "push-actions.json")


def used(nonce: str) -> str | None:
    """What was pressed on this notification already, if anything."""
    value = json_store.read(_used_path(), {})
    entry = value.get(nonce) if isinstance(value, dict) else None
    return entry.get("action") if isinstance(entry, dict) else None


def mark_used(nonce: str, action: str, expires: int) -> None:
    value = json_store.read(_used_path(), {})
    value = {k: v for k, v in (value.items() if isinstance(value, dict) else []) if isinstance(v, dict) and v.get("e", 0) > time.time()}
    value[nonce] = {"action": action, "e": expires}
    json_store.write(_used_path(), dict(list(value.items())[-MAX_USED:]))


def for_task(task_id: str) -> list[dict[str, str]]:
    return [{"id": "done", "title": TITLES["done"]}, {"id": "later", "title": TITLES["later"]}]


def for_inbox(item: dict[str, Any]) -> list[dict[str, str]]:
    """An inbox item's own safe actions (no confirm, not danger), then snooze; two at most."""
    own = [{"id": a["id"], "title": a.get("label") or a["id"]} for a in item.get("actions") or []
           if isinstance(a, dict) and a.get("id") and not a.get("confirm") and a.get("style") != "danger" and a["id"] != "dismiss"]
    return (own + [{"id": "snooze", "title": TITLES["snooze"]}, {"id": "dismiss", "title": TITLES["dismiss"]}])[:2]


async def perform(hub, payload: dict[str, Any], action: str, now: datetime | None = None, pin: str | None = None) -> str:
    """Run one button; returns what happened, in words."""
    if action not in {a["id"] for a in payload.get("a") or []}:
        raise BadToken("That button isn't on this notification.")
    kind, _, ref = str(payload.get("t")).partition(":")
    if kind == "task":
        from app.tasks import service as tasks

        try:
            if action == "done":
                result = await tasks.complete(hub, ref)
                return f"Next one {result['next_due']}." if result.get("action") == "repeated" else "Done."
            if action == "later":
                return later(ref, now)
        except tasks.NotFound as exc:
            raise LookupError(ref) from exc
    if kind == "inbox":
        from app.attention import api as inbox
        from app.attention import service as attention
        from app.brief.service import zone

        if action == "snooze":
            attention.snooze(ref, (now or datetime.now(zone())) + timedelta(hours=3))
            return "Snoozed for 3 hours."
        await inbox.act(ref, inbox.ActRequest(action=action, pin=pin), hub)
        return "Dismissed." if action == "dismiss" else f"{next((a['title'] for a in payload['a'] if a['id'] == action), action)}: done."
    raise BadToken("SirisOS doesn't know what this notification is for.")


def later(task_id: str, now: datetime | None = None) -> str:
    """Move a SirisOS task an hour on, so it notifies again then."""
    from app.brief.service import zone
    from app.tasks import service as tasks
    from app.tasks import store

    at = ((now or datetime.now(zone())).astimezone(zone()) + timedelta(hours=1)).replace(second=0, microsecond=0)
    doc = store.load()
    t = tasks._own(doc, task_id)
    t.due, t.time, t.reminded_for = at.date().isoformat(), at.strftime("%H:%M"), None
    store.save(doc)
    return f"Moved to {at:%H:%M}."
