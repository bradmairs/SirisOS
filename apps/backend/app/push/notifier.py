"""What to notify about, and the background loop that sends it.

Every minute (while at least one device is subscribed) SirisOS works out
the notifications that apply now, skips any already sent (each has a key,
like the inbox's: "app is down" comes back if it goes down again later),
and pushes the rest to every device subscribed to that topic. A device the
push service says is gone is dropped.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.attention import service as attention
from app.brief.service import zone
from app.career import cpd
from app.career import store as career_store
from app.hub.service import Hub, get_hub, shared_client
from app.push import actions, store, webpush

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 60.0


def brief_hour() -> int:
    try:
        return max(0, min(23, int(os.getenv("SIRISOS_PUSH_BRIEF_HOUR", "7"))))
    except ValueError:
        return 7


def message(key: str, topic: str, title: str, body: str = "", url: str = "/", urgency: str = "normal",
            target: str | None = None, actions: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """`target` and `actions` put buttons on it (push/actions.py)."""
    return {"key": key, "topic": topic, "title": title, "body": body, "url": url, "urgency": urgency,
            "target": target, "actions": actions or []}


def inbox_messages(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for item in items:
        if item["severity"] not in ("urgent", "attention"):
            continue
        topic = "apps" if item.get("source") == "hub" else "inbox"
        out.append(message(f"inbox:{item['id']}", topic, item["title"], item.get("body") or "", "/inbox",
                           "high" if item["severity"] == "urgent" else "normal", f"inbox:{item['id']}", actions.for_inbox(item)))
    return out


def brief_message(now: datetime) -> list[dict[str, Any]]:
    if now.hour < brief_hour():
        return []
    return [message(f"brief:{now.date().isoformat()}", "brief", "Your daily brief is ready",
                    "Your day, the news and anything that needs a look.", "/brief")]


def career_messages(doc: career_store.CareerDocument, today: date) -> list[dict[str, Any]]:
    out = []
    for goal in doc.goals:
        if goal.status != "active" or not goal.target_date:
            continue
        try:
            due = date.fromisoformat(goal.target_date)
        except ValueError:
            continue
        if today <= due <= today + timedelta(days=7):
            days = (due - today).days
            when = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"
            out.append(message(f"career:goal:{goal.id}:{goal.target_date}", "career", f"Career goal due {when}",
                               goal.title + (f" · Next: {goal.next_step}" if goal.next_step else ""), "/career"))
    summary = cpd.summary(doc, today)
    if summary["records"] and summary["expiring_90_days"] > 0:
        out.append(message(f"career:expiring:{today.strftime('%Y-%m')}", "career",
                           f"{summary['expiring_90_days']:g} CPD hours drop out of your 3-year window soon",
                           f"You're on {summary['total']:g} of {summary['required']} hours.", "/career"))
    return out


def task_messages(now: datetime) -> list[dict[str, Any]]:
    """A SirisOS task with a time, once, when that time comes (the inbox topic)."""
    from app.tasks import service as tasks

    due = tasks.due_now(now)
    tasks.mark_reminded([t.id for t in due])
    return [message(f"task:{t.id}:{t.due}T{t.time}", "inbox", t.title, "Due now" + (f" · {t.notes}" if t.notes else ""), "/tasks", "high",
                    f"task:sirisos:{t.id}", actions.for_task(t.id))
            for t in due]


async def collect(hub: Hub, now: datetime) -> list[dict[str, Any]]:
    """Every notification that applies right now, sent or not."""
    out: list[dict[str, Any]] = []
    try:
        out += inbox_messages((await attention.inbox(hub))["items"])
    except Exception as exc:  # noqa: BLE001 - one source never stops the others
        logger.info("Push: inbox unavailable: %s", exc)
    out += brief_message(now)
    try:
        from app.wrapup import service as wrapup

        out += wrapup.push_message(now)
        from app.review import service as review

        out += review.push_message(now)
        from app.goals import service as goals

        out += goals.push_message(now)
    except Exception as exc:  # noqa: BLE001
        logger.info("Push: wrap-up unavailable: %s", exc)
    try:
        out += task_messages(now)
    except Exception as exc:  # noqa: BLE001
        logger.info("Push: tasks unavailable: %s", exc)
    try:
        from app.maintenance import service as maintenance

        out += maintenance.push_messages(now)
    except Exception as exc:  # noqa: BLE001
        logger.info("Push: maintenance unavailable: %s", exc)
    try:
        from app.netwatch import service as netwatch

        out += await netwatch.check(hub)
    except Exception as exc:  # noqa: BLE001
        logger.info("Push: network watch unavailable: %s", exc)
    try:
        out += career_messages(career_store.load(), now.date())
    except Exception as exc:  # noqa: BLE001
        logger.info("Push: career unavailable: %s", exc)
    return out


def payload_for(msg: dict[str, Any]) -> dict[str, Any]:
    """What the service worker gets. With buttons, a tap opens the /act page
    (iPhone shows no buttons) and each button posts the signed token."""
    payload = {k: msg[k] for k in ("title", "body", "url")} | {"tag": msg["key"]}
    if msg.get("target") and msg.get("actions"):
        token = actions.sign(msg["target"], msg["actions"], msg["title"], msg["body"], msg["url"])
        payload |= {"actions": [{"action": a["id"], "title": a["title"]} for a in msg["actions"]], "url": f"/act?t={token}"}
    return payload


async def deliver(messages: list[dict[str, Any]]) -> int:
    """Push each message to the subscribed devices; returns how many were sent."""
    subs = store.subscriptions()
    sent_keys: list[str] = []
    count = 0
    client = shared_client()
    for msg in messages:
        targets = [s for s in subs if msg["topic"] in s.topics]
        payload = payload_for(msg)
        for sub in targets:
            try:
                await webpush.send(client, sub.model_dump(), payload, urgency=msg["urgency"])
                store.record(sub.endpoint)
                count += 1
            except webpush.Gone:
                store.remove(sub.endpoint)
                logger.info("Push: dropped a gone subscription (%s)", sub.label or "unnamed")
            except Exception as exc:  # noqa: BLE001 - one device never blocks the rest
                store.record(sub.endpoint, describe(exc))
                logger.warning("Push to %s failed: %s", sub.label or "a device", exc)
        sent_keys.append(msg["key"])
    store.mark_sent(sent_keys)
    return count


def describe(exc: Exception) -> str:
    """A push failure in a line: the push service's status, not its long URL."""
    response = getattr(exc, "response", None)
    if response is not None and getattr(response, "status_code", None):
        code = response.status_code
        why = {401: "the push service turned down SirisOS's signature", 403: "the push service turned down SirisOS's signature",
               413: "the message was too big", 429: "the push service says too many messages"}.get(code, "the push service refused it")
        return f"{why} ({code})"
    return f"{type(exc).__name__}: {str(exc)[:200]}"


QUIET_DAYS = 7


async def check_in(now: datetime) -> int:
    """Once a week, a device nothing has reached for QUIET_DAYS gets a
    'still working' note, so a phone that stopped receiving (a changed key,
    iOS dropping the subscription) shows up as failing instead of silent.
    Web Push on iPhone can't be silent, so it's a real, low-urgency one."""
    cutoff = (now.astimezone(timezone.utc) - timedelta(days=QUIET_DAYS)).isoformat(timespec="seconds")
    health = store.health()
    due = [s for s in store.subscriptions()
           if max((health.get(s.endpoint) or {}).get("last_ok") or "", (health.get(s.endpoint) or {}).get("last_error_at") or "", s.created_at or "") < cutoff]
    if not due:
        return 0
    week = now.strftime("%G-W%V")
    msg = message(f"push-check:{week}", "apps", "SirisOS notifications are working", "A weekly check that this device still gets them.", "/inbox", "very-low")
    sent = 0
    for sub in due:
        try:
            await webpush.send(shared_client(), sub.model_dump(), payload_for(msg), urgency="very-low")
            store.record(sub.endpoint)
            sent += 1
        except webpush.Gone:
            store.remove(sub.endpoint)
        except Exception as exc:  # noqa: BLE001
            store.record(sub.endpoint, describe(exc))
    return sent


async def run_once(hub: Hub, now: datetime | None = None) -> int:
    if not store.subscriptions():
        return 0
    now = now or datetime.now(zone())
    already = store.sent()
    fresh = [m for m in await collect(hub, now) if m["key"] not in already]
    sent = await deliver(fresh)
    try:
        await check_in(now)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Push check-in failed: %s", exc)
    return sent


async def loop() -> None:
    while True:
        try:
            await run_once(get_hub())
        except Exception as exc:  # noqa: BLE001 - keep the loop alive
            logger.warning("Push loop failed: %s", exc)
        await asyncio.sleep(INTERVAL_SECONDS)


def enabled() -> bool:
    return os.getenv("SIRISOS_PUSH_ENABLED", "1") not in ("0", "false", "no")
