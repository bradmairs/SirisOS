"""The inbox (ADR 110): everything that needs Brad, from every app, in one list.

Two sources, merged:

- **SirisAI's attention feed** (`/siris/hub/v1/attention`): its alerts
  (intruders, failed self-heals, security), actions waiting for approval,
  habit suggestions, jobs waiting for cheap power, Siris reviews.
  Their actions (Approve, Lock down, Create automation...) are SirisAI's and
  run there; SirisOS only relays them. Ids are prefixed `ai:`.
- **SirisOS's own**, from what the hub already watches (ids `os:`): any app
  that's down or degraded, the
  Engineering Archive's review queue, and a SirisLearn streak that ends at
  midnight unless today's quiz is done (ADR 112). Their only action is Dismiss; tapping
  opens the app. A dismissal is remembered (server-side, so every device
  agrees) until the situation changes -- the item's key includes its state
  or count, so "the Archive is down" comes back if it goes down again tomorrow,
  and "3 waiting for review" comes back as "4 waiting".

Each source fails alone: a SirisAI outage leaves SirisOS's own items (and
an "apps down" item for SirisAI itself), and the reverse.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.hub.connectors.sirisai import SirisAIConnector
from app.hub.service import Hub, shared_client

logger = logging.getLogger(__name__)

SEVERITIES = ("urgent", "attention", "info")
MAX_DISMISSED = 500


def _state_path() -> Path:
    return Path(os.getenv("SIRISOS_ATTENTION_STATE_PATH", "/app/data/attention-state.json"))


def _state() -> dict[str, Any]:
    try:
        value = json.loads(_state_path().read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_state(state: dict[str, Any]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    tmp.replace(path)


def _dismissed() -> list[str]:
    value = _state().get("dismissed")
    return value if isinstance(value, list) else []


def dismiss_local(key: str) -> None:
    state = _state()
    keys = [k for k in _dismissed() if k != key] + [key]
    state["dismissed"] = keys[-MAX_DISMISSED:]
    _write_state(state)


def snoozed() -> dict[str, str]:
    """Inbox items put off until a time (ISO, UTC), live ones only."""
    now = datetime.now(timezone.utc).isoformat()
    value = _state().get("snoozed")
    return {k: v for k, v in (value.items() if isinstance(value, dict) else []) if isinstance(v, str) and v > now}


def snooze(item_id: str, until: datetime) -> str:
    state = _state()
    live = snoozed()
    live[item_id] = until.astimezone(timezone.utc).isoformat(timespec="seconds")
    state["snoozed"] = dict(list(live.items())[-MAX_DISMISSED:])
    _write_state(state)
    return live[item_id]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _metric(widget: dict[str, Any] | None, label: str) -> int:
    for m in (widget or {}).get("metrics") or []:
        if m.get("label") == label:
            try:
                return int(str(m.get("value")).replace(",", ""))
            except ValueError:
                return 0
    return 0


def own_items(apps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """SirisOS's items from the hub's app list (with widgets), before dismissals."""
    items: list[dict[str, Any]] = []
    day = datetime.now(timezone.utc).date().isoformat()
    for app in apps:
        status = app.get("status") or {}
        state = status.get("state")
        if state in ("down", "degraded"):
            items.append({
                "key": f"app:{app['id']}:{state}",
                "kind": "alert",
                "severity": "attention" if state == "down" else "info",
                "title": f"{app['name']} is {state}",
                "body": status.get("detail") or "",
                "source": "hub",
                "app": app["name"],
                "url": app.get("launch_url"),
            })
        widget = app.get("widget") if isinstance(app.get("widget"), dict) else None
        if app.get("id") == "archive" and (review := _metric(widget, "Needs review")):
            items.append({
                "key": f"archive:review:{review}",
                "kind": "review",
                "severity": "info",
                "title": f"{review} item{'s' if review != 1 else ''} waiting for review in the {app['name']}",
                "body": "",
                "source": "archive",
                "app": app["name"],
                "url": app.get("launch_url"),
            })
        if app.get("id") == "sirislearn" and (streak := _streak_at_risk(widget)):
            items.append({
                "key": f"sirislearn:streak:{day}",
                "kind": "notice",
                "severity": "info",
                "title": f"Your {streak}-day learning streak ends at midnight",
                "body": "Finish a quiz in SirisLearn today to keep it going.",
                "source": "sirislearn",
                "app": app["name"],
                "url": next((i.get("url") for i in (widget or {}).get("items") or [] if i.get("url")), app.get("launch_url")),
            })
    return items


def _streak_at_risk(widget: dict[str, Any] | None) -> int:
    """SirisLearn's streak length when its Streak metric is flagged (tone warning)."""
    for m in (widget or {}).get("metrics") or []:
        if m.get("label") == "Streak" and m.get("tone") == "warning":
            digits = "".join(ch for ch in str(m.get("value")).split(" ")[0] if ch.isdigit())
            return int(digits) if digits else 0
    return 0


def from_os(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"os:{item['key']}",
        "origin": "sirisos",
        "kind": item["kind"],
        "severity": item["severity"],
        "title": item["title"],
        "body": item.get("body") or "",
        "source": item["source"],
        "app": item.get("app") or "SirisOS",
        "url": item.get("url"),
        "link": None,
        "actions": [],
        "created_at": _now(),
        "updated_at": _now(),
    }


def from_ai(item: dict[str, Any]) -> dict[str, Any]:
    """One SirisAI AttentionItem (contract v1) as an inbox item."""
    return {
        "id": f"ai:{item['id']}",
        "origin": "sirisai",
        "kind": item.get("kind", "notice"),
        "severity": item.get("severity", "attention"),
        "title": item.get("title", ""),
        "body": item.get("body") or "",
        "source": item.get("source", "siris"),
        "app": "SirisAI",
        "url": None,
        "link": item.get("link"),
        "actions": item.get("actions") or [],
        "created_at": item.get("created_at") or _now(),
        "updated_at": item.get("updated_at") or _now(),
    }


def sort_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Urgent first, then attention, then info; newest first within each."""
    newest = sorted(items, key=lambda i: i["updated_at"], reverse=True)
    return sorted(newest, key=lambda i: SEVERITIES.index(i["severity"]) if i["severity"] in SEVERITIES else 9)


def counts(items: list[dict[str, Any]]) -> dict[str, int]:
    return {"open": len(items), "urgent": sum(1 for i in items if i["severity"] == "urgent")}


def sirisai(hub: Hub) -> SirisAIConnector | None:
    connector = hub.get("sirisai")
    return connector if isinstance(connector, SirisAIConnector) and connector.configured else None


async def ai_items(hub: Hub) -> list[dict[str, Any]] | None:
    """SirisAI's open items, or None if SirisAI isn't configured, is too old
    to have the feed, or didn't answer."""
    connector = sirisai(hub)
    if connector is None:
        return None
    response = await shared_client().get(f"{connector.base_url}/siris/hub/v1/attention", headers=connector.headers(), timeout=8.0)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return [from_ai(i) for i in response.json().get("items") or []]


def backup_items() -> list[dict[str, Any]]:
    """SirisOS's own backup failing or going stale (3.7); nothing before the first one."""
    from app.backup import service as backup

    s = backup.status()
    if not s["enabled"] or not (s["error"] or (s["stale"] and s["newest"])):
        return []
    day = datetime.now(timezone.utc).date().isoformat()
    return [{
        "key": f"backup:{'error' if s['error'] else 'stale'}:{day}",
        "kind": "alert",
        "severity": "attention",
        "title": "SirisOS's backup failed" if s["error"] else "SirisOS hasn't backed up in over a day",
        "body": s["error"] or f"Newest backup {s['newest'][:16].replace('T', ' ')} UTC, in {s['folder']}.",
        "source": "backups",
        "app": "SirisOS",
        "url": "/status",
    }]


async def os_items(hub: Hub) -> list[dict[str, Any]]:
    dismissed = set(_dismissed())
    apps = await hub.apps(with_widgets=True)
    return [from_os(i) for i in own_items(apps) + backup_items() if f"os:{i['key']}" not in dismissed]


async def inbox(hub: Hub) -> dict[str, Any]:
    failed: list[str] = []
    mine = []
    try:
        mine = await os_items(hub)
    except Exception as exc:  # noqa: BLE001 - one source never empties the inbox
        logger.info("SirisOS inbox items unavailable: %s", exc)
        failed.append("SirisOS")
    theirs: list[dict[str, Any]] = []
    try:
        theirs = await ai_items(hub) or []
    except Exception as exc:  # noqa: BLE001
        logger.info("SirisAI attention feed unavailable: %s", exc)
        failed.append("SirisAI")
    later = snoozed()
    items = sort_items([i for i in theirs + mine if i["id"] not in later])
    if not failed:
        from app.trends import log

        log.inbox(len(items))
    return {"items": items, "counts": counts(items), "unavailable": failed, "snoozed": len(later)}
