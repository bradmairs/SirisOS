"""Smarter notifications (10.6): fewer, and the right ones.

Every notification SirisOS would send passes through `route` first:

1. **Seen already:** each card in the app reports the notification key it stands for once it's been on screen
   (POST /api/v1/push/seen). A notification whose key has been seen isn't sent, and a held one is dropped.
2. **Still true:** before a held notification goes out it's checked again (an inbox item still open, the garden
   still not watered). If it no longer applies it's dropped.
3. **In the app now:** while SirisOS is open on any device (a heartbeat in the last few minutes), non-urgent
   notifications show as a banner in the app instead of a push.
4. **One device:** a push goes to the device used most recently, not all of them. Urgent ones go everywhere.
5. **Asleep or busy:** between tonight's bedtime and waking (Health), non-urgent ones wait for the morning roundup;
   during a calendar event or a focus block they wait until it ends.
6. **Home things at home:** bins, garden and bedroom notifications wait until someone's home (SirisAI presence).
7. **Learns what's ignored:** five pushes of a kind in a row that weren't opened (or seen in the app) move that kind
   to the roundup. Each kind can be set to normal, roundup only or off; the week's numbers are in the report.
8. **A daily cap and replacing:** at most `cap` non-urgent pushes a day (the rest wait for a roundup), and a newer
   notification of the same kind replaces the last one on the lock screen.

Urgent ones and those at a time you chose (a task, the fuel stop, bedtime nudges, travel) still come straight away,
unless you've already seen them. Kept in push-smart.json.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.services import json_store

logger = logging.getLogger(__name__)

ACTIVE_MINUTES = 5
DEFAULT_CAP = 6
IGNORED_AFTER_HOURS = 12
IGNORED_STREAK = 5
LATER_HOURS = 18
# At a time you chose: never held for sleep, meetings or the cap, never moved to the roundup by being ignored.
EXPLICIT = ("task", "fuel", "nudge", "sirisai-wind-down", "travel", "push-check", "timesheet", "cashflow", "bedroom")
HOME_ONLY = ("bins", "garden", "bedroom")
# One notification per item: these never replace each other on the lock screen.
PER_ITEM = ("inbox", "task", "renewal", "homejob")
LABELS = {
    "inbox": "Inbox and app alerts", "brief": "Daily brief", "task": "Tasks at their time", "nudge": "Nudges (bedtime, breaks)",
    "sirisai-wind-down": "Wind down", "digest": "Roundups", "wrapup": "Wrap up your day", "work-wrapup": "Wrap up work",
    "review": "Weekly review", "recap": "Monthly recap", "timesheet": "Timesheet reminder", "cashflow": "Money before pay",
    "renewal": "Renewals", "homejob": "Jobs around the house", "travel": "Trips", "fuel": "Fuel on the way",
    "bins": "Bin night", "garden": "Garden", "bedroom": "Bedroom before bed", "weekend": "Weekend outside",
    "catchup": "Catch-ups", "internet-slow": "Slow internet", "netdev": "New network devices", "career": "Career",
    "gym": "SirisGym", "push-check": "Weekly 'still working' check",
}
_HHMM = re.compile(r"(?:T|\b)([01]\d|2[0-3]):([0-5]\d)")


def _path():
    return json_store.data_path("SIRISOS_PUSH_SMART_PATH", "push-smart.json")


def load() -> dict[str, Any]:
    doc = json_store.read(_path(), {}) or {}
    for k, v in (("on", True), ("cap", DEFAULT_CAP), ("seen", {}), ("active", {}), ("busy_until", None), ("inapp", []),
                 ("later", []), ("kinds", {}), ("pending", {}), ("log", []), ("today", {"date": None, "count": 0}), ("context", {})):
        doc.setdefault(k, v)
    return doc


def save(doc: dict[str, Any]) -> None:
    json_store.write(_path(), doc)


def kind(key: str) -> str:
    return str(key).split(":", 1)[0]


def _utc(now: datetime) -> datetime:
    return now.astimezone(timezone.utc)


def _iso(now: datetime) -> str:
    return _utc(now).isoformat(timespec="seconds")


def _parse(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# -- what the app tells us ------------------------------------------------------------------------------------------

def mark_seen(keys: list[str], now: datetime) -> int:
    """Cards on screen. A pending push of the same key counts as opened (you saw it in the app)."""
    doc = load()
    at = _iso(now)
    keys = [k for k in dict.fromkeys(keys) if isinstance(k, str) and 0 < len(k) <= 160][:50]
    for k in keys:
        doc["seen"][k] = at
        _engaged(doc, k)
    doc["inapp"] = [m for m in doc["inapp"] if m["key"] not in keys]
    cutoff = _iso(now - timedelta(days=21))
    doc["seen"] = {k: v for k, v in doc["seen"].items() if v >= cutoff}
    save(doc)
    return len(keys)


def opened(key: str, now: datetime) -> bool:
    doc = load()
    if key not in doc["pending"]:
        return False
    _engaged(doc, key)
    doc["seen"][key] = _iso(now)
    save(doc)
    return True


def _engaged(doc: dict[str, Any], key: str) -> None:
    if key in doc["pending"]:
        doc["pending"].pop(key)
        k = doc["kinds"].setdefault(kind(key), {})
        k["opened"] = k.get("opened", 0) + 1
        k["streak"] = 0
        _log(doc, key, "opened")


def heartbeat(device: str, endpoint: str | None, label: str | None, focus_until: str | None, now: datetime) -> list[dict[str, Any]]:
    """The app is open on this device. Returns the banners waiting to show."""
    doc = load()
    doc["active"][device[:80]] = {"at": _iso(now), "endpoint": endpoint, "label": (label or "")[:60]}
    cutoff = _iso(now - timedelta(days=30))
    doc["active"] = {k: v for k, v in doc["active"].items() if v["at"] >= cutoff}
    until = _parse(focus_until)
    if until and until > _utc(now):
        doc["busy_until"] = _utc(until).isoformat(timespec="seconds")
    elif focus_until is None and doc.get("busy_source") == device:
        doc["busy_until"] = None
    if until:
        doc["busy_source"] = device
    doc["inapp"] = [m for m in doc["inapp"] if m["at"] >= _iso(now - timedelta(hours=12))]
    save(doc)
    return list(doc["inapp"])


def using_now(doc: dict[str, Any], now: datetime) -> bool:
    cutoff = _iso(now - timedelta(minutes=ACTIVE_MINUTES))
    return any(v["at"] >= cutoff for v in doc["active"].values())


def latest_endpoint(doc: dict[str, Any]) -> str | None:
    """The subscribed device used most recently, if the app knows its push endpoint."""
    have = [v for v in doc["active"].values() if v.get("endpoint")]
    return max(have, key=lambda v: v["at"])["endpoint"] if have else None


# -- context: asleep, busy, at home ------------------------------------------------------------------------------------

async def context(hub: Any, now: datetime) -> dict[str, Any]:
    """Bedtime, waking time, today's timed events and presence, from SirisAI. Kept ten minutes (only asked when
    there's something to send)."""
    from app.hub import sirisai_api

    doc = load()
    ctx = doc["context"]
    if ctx.get("at") and ctx["at"] >= _iso(now - timedelta(minutes=10)):
        return ctx
    local = now
    day = local.date()
    try:
        health = await sirisai_api.get(hub, "/siris/hub/v1/health/overview", timeout=8.0) or {}
    except Exception:  # noqa: BLE001
        health = {}
    try:
        cal = await sirisai_api.get(hub, "/siris/hub/v1/calendar", params={"start": day.isoformat(), "end": (day + timedelta(days=1)).isoformat()}, timeout=8.0) or {}
    except Exception:  # noqa: BLE001
        cal = {}
    try:
        presence = await sirisai_api.get(hub, "/siris/hub/v1/presence", timeout=5.0)
    except Exception:  # noqa: BLE001
        presence = None
    bed = _hhmm(((health.get("bedtime") or {}).get("bedtime")) if isinstance(health.get("bedtime"), dict) else None)
    wake = _hhmm((((health.get("sleep") or {}).get("last_night") or {}).get("end")) if isinstance(health.get("sleep"), dict) else None)
    events = [{"start": e["start"], "end": e["end"]} for e in (cal.get("events") or [])
              if isinstance(e, dict) and e.get("start") and e.get("end") and not e.get("all_day") and "T" in str(e["start"])]
    ctx = {"at": _iso(now), "bed": bed or "22:30", "wake": wake or "06:30", "events": events,
           "home": (presence or {}).get("home") if isinstance(presence, dict) else None}
    doc["context"] = ctx
    save(doc)
    return ctx


def _hhmm(text: str | None) -> str | None:
    m = _HHMM.search(text or "")
    return f"{m.group(1)}:{m.group(2)}" if m else None


def asleep(ctx: dict[str, Any], local: datetime) -> bool:
    t, bed, wake = local.strftime("%H:%M"), ctx.get("bed") or "22:30", ctx.get("wake") or "06:30"
    # Half an hour's grace after bedtime for the wind-down; waking is the end of last night's sleep.
    return (t >= bed or t < wake) if bed > wake else (bed <= t < wake)


def busy_until(doc: dict[str, Any], ctx: dict[str, Any], now: datetime) -> datetime | None:
    """The end of a meeting or focus block happening now."""
    ends = []
    focus = _parse(doc.get("busy_until"))
    if focus and focus > _utc(now):
        ends.append(focus)
    for e in ctx.get("events") or []:
        s, f = _parse(e["start"]), _parse(e["end"])
        if s and f and s <= _utc(now) < f and f - s <= timedelta(hours=10):
            ends.append(f)
    return max(ends) if ends else None


# -- per kind: how it's going, and your choice --------------------------------------------------------------------------

def mode(doc: dict[str, Any], k: str) -> str:
    """normal | roundup | off: your choice, or roundup when it's been ignored."""
    entry = doc["kinds"].get(k) or {}
    choice = entry.get("mode") or "auto"
    if choice != "auto":
        return choice
    return "roundup" if entry.get("demoted") and not k.startswith(EXPLICIT) else "normal"


def set_mode(k: str, choice: str) -> dict[str, Any]:
    if choice not in ("auto", "normal", "roundup", "off"):
        raise ValueError("Choose auto, normal, roundup or off.")
    doc = load()
    entry = doc["kinds"].setdefault(k, {})
    entry["mode"] = choice
    if choice in ("auto", "normal"):
        entry["demoted"] = False
        entry["streak"] = 0
    save(doc)
    return report(datetime.now(timezone.utc))


def change(on: bool | None = None, cap: int | None = None) -> None:
    doc = load()
    if on is not None:
        doc["on"] = on
    if cap is not None:
        doc["cap"] = max(1, min(30, int(cap)))
    save(doc)


def _ignored(doc: dict[str, Any], now: datetime) -> None:
    """Pushes not opened within IGNORED_AFTER_HOURS count against their kind."""
    cutoff = _iso(now - timedelta(hours=IGNORED_AFTER_HOURS))
    for key, at in list(doc["pending"].items()):
        if at < cutoff:
            doc["pending"].pop(key)
            entry = doc["kinds"].setdefault(kind(key), {})
            entry["streak"] = entry.get("streak", 0) + 1
            entry["ignored"] = entry.get("ignored", 0) + 1
            if entry["streak"] >= IGNORED_STREAK and not kind(key).startswith(EXPLICIT) and (entry.get("mode") or "auto") == "auto":
                if not entry.get("demoted"):
                    entry["demoted"] = True
                    entry["demoted_at"] = _iso(now)
            _log(doc, key, "ignored")


def _log(doc: dict[str, Any], key: str, what: str, now: datetime | None = None) -> None:
    doc["log"] = [*doc["log"], {"key": key, "what": what, "at": _iso(now or datetime.now(timezone.utc))}][-800:]


# -- the routing ------------------------------------------------------------------------------------------------------

async def still_true(hub: Any, msgs: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    """Drop held notifications that no longer apply."""
    if not msgs:
        return msgs
    keep = msgs
    if any(kind(m["key"]) == "inbox" for m in msgs):
        try:
            from app.attention import service as attention

            open_ids = {f"inbox:{i['id']}" for i in (await attention.inbox(hub))["items"]}
            keep = [m for m in keep if kind(m["key"]) != "inbox" or m["key"] in open_ids]
        except Exception:  # noqa: BLE001 - can't check: keep it
            pass
    if any(kind(m["key"]) == "garden" for m in keep):
        from app.outdoors import garden

        if garden.load().get("last_watered") == today.isoformat():
            keep = [m for m in keep if kind(m["key"]) != "garden"]
    return keep


def seen_filter(doc: dict[str, Any], msgs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [m for m in msgs if m["key"] not in doc["seen"]]


async def route(hub: Any, fresh: list[dict[str, Any]], now: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Sort new notifications: (send now, for the roundup, keys done with). Waiting ones are kept here."""
    from app.push import digest

    doc = load()
    done: list[str] = []
    if not doc["on"]:
        now_, later = digest.split(fresh)
        return now_, later, []
    if not fresh and not _any_due(doc, now):
        _ignored(doc, now)
        save(doc)
        return [], [], []
    ctx = await context(hub, now)
    doc = load()  # context() saved it
    _ignored(doc, now)
    released = await still_true(hub, seen_filter(doc, _release(doc, now)), now.date())
    candidates = fresh + released
    send, roundup = [], []
    local = now
    for m in candidates:
        k = kind(m["key"])
        urgent = m.get("urgency") == "high"
        explicit = k.startswith(EXPLICIT)
        choice = mode(doc, k)
        if choice == "off" and not urgent:
            done.append(m["key"]); _log(doc, m["key"], "off", now)
            continue
        if m["key"] in doc["seen"]:
            done.append(m["key"]); _log(doc, m["key"], "seen", now)
            continue
        if urgent:
            send.append(m)
            continue
        if k in HOME_ONLY and ctx.get("home") is False:
            _later(doc, m, now, need_home=True); done.append(m["key"]); _log(doc, m["key"], "waiting for home", now)
            continue
        if not explicit and asleep(ctx, local):
            roundup.append(m); _log(doc, m["key"], "asleep: morning roundup", now)
            continue
        if not explicit:
            until = busy_until(doc, ctx, now)
            if until:
                _later(doc, m, now, until=until); done.append(m["key"]); _log(doc, m["key"], "busy: after", now)
                continue
        if choice == "roundup":
            roundup.append(m); _log(doc, m["key"], "roundup", now)
            continue
        send.append(m)
    save(doc)
    # The roundup's own rules (what can wait) for the rest, then the cap.
    straight, wait = digest.split(send)
    roundup += wait
    return straight, roundup, done


def _later(doc: dict[str, Any], m: dict[str, Any], now: datetime, until: datetime | None = None, need_home: bool = False) -> None:
    if any(x["msg"]["key"] == m["key"] for x in doc["later"]):
        return
    doc["later"].append({"msg": {k: m.get(k) for k in ("key", "topic", "title", "body", "url", "urgency")},
                         "until": _utc(until).isoformat(timespec="seconds") if until else None, "home": need_home, "at": _iso(now)})


def _any_due(doc: dict[str, Any], now: datetime) -> bool:
    home = (doc.get("context") or {}).get("home")
    # Someone waiting for home: ask again (presence is kept ten minutes, so this is cheap).
    return any((x.get("until") and x["until"] <= _iso(now)) or x.get("home") for x in doc["later"])


def _release(doc: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
    """Waiting notifications whose wait is over: the meeting ended, or someone's home. Old ones lapse."""
    out, keep = [], []
    home = (doc.get("context") or {}).get("home")
    for x in doc["later"]:
        if x["at"] < _iso(now - timedelta(hours=LATER_HOURS)):
            continue
        over = (x.get("until") and x["until"] <= _iso(now)) or (x.get("home") and home is not False)
        (out if over else keep).append(x)
    doc["later"] = keep
    return [x["msg"] | {"target": None, "actions": []} for x in out]


def deliver_plan(msgs: list[dict[str, Any]], now: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Of the notifications to send now: (push, banner in the app). Also applies the daily cap; what's over it
    goes back for the roundup (returned in push with `hold: True`)."""
    doc = load()
    if not doc["on"]:
        return msgs, []
    push, banners = [], []
    local_day = now.date().isoformat()
    if doc["today"].get("date") != local_day:
        doc["today"] = {"date": local_day, "count": 0}
    active = using_now(doc, now)
    for m in msgs:
        urgent = m.get("urgency") == "high"
        if m["key"] in doc["seen"]:
            continue
        if active and not urgent:
            banners.append(m)
            continue
        if not urgent and not kind(m["key"]).startswith(EXPLICIT) and not m["key"].startswith("digest:") and doc["today"]["count"] >= doc["cap"]:
            push.append(m | {"hold": True})
            continue
        if not urgent:
            doc["today"]["count"] += 1
        push.append(m)
    at = _iso(now)
    have = {b["key"] for b in doc["inapp"]}
    doc["inapp"] = [*doc["inapp"], *({"key": b["key"], "title": b["title"], "body": b.get("body") or "", "url": b.get("url") or "/", "at": at}
                                     for b in banners if b["key"] not in have)][-20:]
    for b in banners:
        _log(doc, b["key"], "in the app", now)
    save(doc)
    return push, banners


def targets(subs: list[Any], msg: dict[str, Any]) -> list[Any]:
    """Every device for urgent ones; otherwise the one used most recently (when the app knows it)."""
    if msg.get("urgency") == "high":
        return subs
    doc = load()
    if not doc["on"]:
        return subs
    latest = latest_endpoint(doc)
    one = [s for s in subs if s.endpoint == latest]
    return one or subs


def pushed(keys: list[str], now: datetime) -> None:
    doc = load()
    at = _iso(now)
    for key in keys:
        entry = doc["kinds"].setdefault(kind(key), {})
        entry["sent"] = entry.get("sent", 0) + 1
        doc["pending"][key] = at
        _log(doc, key, "pushed", now)
    save(doc)


def tag(msg: dict[str, Any]) -> str:
    """The lock-screen slot: a newer one of the same kind replaces the last, except per-item kinds."""
    k = kind(msg["key"])
    return msg["key"] if k in PER_ITEM or msg["key"].startswith("digest:") or msg["key"].startswith("push-check:") else f"kind:{k}"


def tick(now: datetime) -> None:
    doc = load()
    _ignored(doc, now)
    save(doc)


def report(now: datetime) -> dict[str, Any]:
    """The last seven days: per kind, pushed, opened (or seen in the app), ignored and how many were spared."""
    doc = load()
    cutoff = _iso(now - timedelta(days=7))
    week: dict[str, dict[str, int]] = {}
    for e in doc["log"]:
        if e["at"] < cutoff:
            continue
        w = week.setdefault(kind(e["key"]), {"pushed": 0, "opened": 0, "ignored": 0, "spared": 0})
        if e["what"] in ("pushed", "opened", "ignored"):
            w[e["what"]] += 1
        elif e["what"] in ("seen", "off", "in the app") or e["what"].startswith(("roundup", "asleep", "busy", "waiting")):
            w["spared"] += 1
    kinds = sorted(set(week) | {k for k, v in doc["kinds"].items() if v.get("mode") not in (None, "auto") or v.get("demoted")})
    rows = []
    for k in kinds:
        entry = doc["kinds"].get(k) or {}
        w = week.get(k) or {"pushed": 0, "opened": 0, "ignored": 0, "spared": 0}
        rows.append({"kind": k, "label": LABELS.get(k, k.replace("-", " ").capitalize()), **w, "mode": entry.get("mode") or "auto",
                     "effective": mode(doc, k), "demoted": bool(entry.get("demoted")), "explicit": k.startswith(EXPLICIT)})
    rows.sort(key=lambda r: (-r["pushed"], r["label"]))
    totals = {x: sum(r[x] for r in rows) for x in ("pushed", "opened", "ignored", "spared")}
    return {"on": doc["on"], "cap": doc["cap"], "kinds": rows, "week": totals, "using_now": using_now(doc, now),
            "devices": len(doc["active"]), "waiting": len(doc["later"])}


async def prune_held(hub: Any, held: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    """The roundup's waiting notifications, less those seen or no longer true."""
    doc = load()
    if not doc["on"]:
        return held
    keep = seen_filter(doc, held)
    for m in held:
        if m not in keep:
            _log(doc, m["key"], "seen")
    save(doc)
    return await still_true(hub, keep, today)
