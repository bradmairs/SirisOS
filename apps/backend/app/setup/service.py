"""The setup checklist (5.6), on System status: everything SirisOS can do
that needs switching on, tested live, with the fix in plain words.

Each check answers one of:
- **on**: working, with what it found;
- **off**: not set up yet (not broken; some you may never want);
- **problem**: set up but failing, or set up unsafely;
and says what to change and where. The settings named are environment
variables: SirisOS's in its `.env`, SirisAI's in SirisAI's. Nothing here
changes anything.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from app.hub import sirisai_api
from app.hub.service import Hub

NEEDS_SIRISAI = "4.03"


def _item(id_: str, title: str, area: str, state: str, detail: str, fix: str = "", settings: list[str] | None = None,
          link: str | None = None) -> dict[str, Any]:
    return {"id": id_, "title": title, "area": area, "state": state, "detail": detail, "fix": fix,
            "settings": settings or [], "link": link}


def _version_at_least(v: str | None, want: str) -> bool:
    try:
        return [int(x) for x in str(v).split(".")[:2]] >= [int(x) for x in want.split(".")[:2]]
    except ValueError:
        return False


def _recent(iso: str | None, days: int) -> bool:
    try:
        when = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return False
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - when <= timedelta(days=days)


async def sirisai(hub: Hub) -> list[dict[str, Any]]:
    c = sirisai_api.connector(hub)
    if c is None:
        return [_item("sirisai", "SirisAI", "SirisAI", "off", "SirisOS isn't connected to SirisAI, so the brain, calendar, health and home features are off.",
                      "Set SirisAI's address and its API key in SirisOS, then restart it.", ["SIRISAI_URL", "SIRISAI_API_KEY"])]
    info, status = await asyncio.gather(sirisai_api.get(hub, "/siris/hub/v1"), _app_status(hub, "sirisai"))
    version = (status or {}).get("version")
    if info is None:
        return [_item("sirisai", "SirisAI", "SirisAI", "problem", f"SirisAI didn't answer at {c.base_url}.",
                      "Check SirisAI is running, the address is right, and SIRISAI_API_KEY matches SirisAI's own key.", ["SIRISAI_URL", "SIRISAI_API_KEY"])]
    if version and not _version_at_least(version, NEEDS_SIRISAI):
        return [_item("sirisai", "SirisAI", "SirisAI", "problem", f"Connected, but it's {version}: this SirisOS expects {NEEDS_SIRISAI} or later (background container updates, overnight readiness, energy).",
                      "Update SirisAI: on the server, in SirisAI's deploy folder, run make update (it pulls both apps and rebuilds; make up alone rebuilds the old code).")]
    return [_item("sirisai", "SirisAI", "SirisAI", "on", f"Connected{f', version {version}' if version else ''}{', guest mode on' if info.get('guest_mode') else ''}.")]


async def _app_status(hub: Hub, app_id: str) -> dict[str, Any] | None:
    try:
        for a in await hub.apps():
            if a.get("id") == app_id:
                return a.get("status") or {}
    except Exception:  # noqa: BLE001
        return None
    return None


async def home(hub: Hub) -> list[dict[str, Any]]:
    if sirisai_api.connector(hub) is None:
        return []
    controls, network, energy = await asyncio.gather(
        sirisai_api.get(hub, "/siris/hub/v1/controls"),
        sirisai_api.get(hub, "/siris/hub/v1/network"),
        sirisai_api.get(hub, "/siris/hub/v1/energy/usage"),
    )
    out = []
    if controls is None or not controls.get("configured"):
        out.append(_item("home-assistant", "Home Assistant", "Smart home", "off" if controls else "problem",
                         "SirisAI isn't connected to Home Assistant: no home controls, protocols or power." if controls else "SirisAI couldn't reach Home Assistant.",
                         "In SirisAI, set Home Assistant's address and a long-lived access token (Home Assistant → your profile → Security).",
                         ["SIRISAI_HOME_ASSISTANT_BASE_URL", "SIRISAI_HOME_ASSISTANT_TOKEN"], "/house"))
    else:
        out.append(_item("home-assistant", "Home Assistant", "Smart home", "on", f"{len(controls.get('controls') or [])} controls and {len(controls.get('scenes') or [])} scenes.", link="/house"))
    if network is None or not network.get("configured"):
        out.append(_item("unifi", "UniFi network", "Smart home", "off" if network else "problem",
                         "No live network: the house has no traffic links and network alerts are off." if network else "SirisAI couldn't read the UniFi gateway.",
                         "In SirisAI, set the Cloud Gateway Ultra's local address and an API key (UniFi Network → Settings → Control Plane → Integrations).",
                         ["SIRISAI_UNIFI_BASE_URL", "SIRISAI_UNIFI_API_KEY"], "/house?view=network"))
    else:
        clients = sum(1 for n in network.get("nodes") or [] if n.get("kind") == "client")
        out.append(_item("unifi", "UniFi network", "Smart home", "on", f"{len(network.get('nodes') or [])} devices on the network ({clients} clients).", link="/house?view=network"))
    if energy is None:
        out.append(_item("power", "Power use", "Smart home", "off", "Power use needs SirisAI 3.11 or later with Home Assistant.", "Update SirisAI.", link="/house"))
    elif not energy.get("configured"):
        out.append(_item("power", "Power use", "Smart home", "off", "Power use needs Home Assistant (above).", link="/house"))
    elif not energy.get("power") and not energy.get("meters"):
        out.append(_item("power", "Power use", "Smart home", "off", "Home Assistant has no power sensors or energy meters yet.",
                         "Add smart plugs with power monitoring, or a whole-house energy monitor, to Home Assistant.", link="/house"))
    else:
        exact = energy.get("house_meter") or energy.get("house_watts") is not None
        out.append(_item("power", "Power use", "Smart home", "on",
                         f"{len(energy.get('power') or [])} power sensors and {len(energy.get('meters') or [])} meters."
                         + ("" if exact else " Today's kWh is added up from all of them; name the whole-house ones for a truer figure."),
                         "" if exact else "In SirisAI, name the whole house's power sensor and kWh meter.",
                         [] if exact else ["SIRISAI_ENERGY_GRID_ENTITY_ID", "SIRISAI_ENERGY_METER_ENTITY_ID"], "/house"))
    return out


async def health(hub: Hub) -> list[dict[str, Any]]:
    from app.training import health_import

    s = health_import.status()
    days = await sirisai_api.get(hub, "/siris/hub/v1/health/days", params={"days": 3}) if sirisai_api.connector(hub) else None
    recent = bool([d for d in (days or {}).get("days") or [] if d.get("metrics")])
    if s["last_ok"] and _recent(s["last_ok"]["at"], 2):
        return [_item("health", "Apple Health", "You", "on", "Arriving on its own from your iPhone.", link="/training#health")]
    if s["has_key"]:
        return [_item("health", "Apple Health", "You", "problem",
                      "A key is made, but nothing has arrived in two days." + (f" The last try said: {s['last']['error']}" if (s.get("last") or {}).get("error") else ""),
                      "Open Health Auto Export on the iPhone: check its REST API automation has the address and the Authorization header, and unlock the phone so it can send.",
                      link="/training#health")]
    return [_item("health", "Apple Health", "You", "on" if recent else "off",
                  "Health data is reaching SirisAI another way." if recent else "Nothing from Apple Health yet: Training, fitness and recovery have nothing to go on.",
                  "" if recent else "On the Training page, make a key and set up Health Auto Export (it takes five minutes).", link="/training#health")]


def push() -> list[dict[str, Any]]:
    from app.push import store

    subs = store.subscriptions()
    if not subs:
        return [_item("push", "Phone notifications", "You", "off", "No device gets notifications: no network alerts, home jobs or approvals on the phone.",
                      "On your iPhone: add SirisOS to the Home Screen, open it from there, then Inbox → Notifications → turn on.", link="/inbox")]
    without_home = [s.label or "a device" for s in subs if "home" not in s.topics]
    health = store.health()
    broken = [(s.label or "a device", (health.get(s.endpoint) or {}).get("last_error") or "") for s in subs if store.failing(s, health.get(s.endpoint) or {})]
    if broken:
        return [_item("push", "Phone notifications", "You", "problem",
                      "Not reaching " + "; ".join(f"{label} ({why})" for label, why in broken) + ".",
                      "On that device: Inbox → Notifications → Turn off, then turn on again.", link="/inbox")]
    return [_item("push", "Phone notifications", "You", "on",
                  f"{len(subs)} device{'s' if len(subs) != 1 else ''}." + (f" {', '.join(without_home)} skips home alerts (network, jobs, power)." if without_home else ""),
                  link="/inbox")]


def backups() -> list[dict[str, Any]]:
    from app.backup import service

    if not service.enabled():
        return [_item("backups", "Nightly backups", "SirisOS", "off", "SirisOS doesn't back up its own data.", "Turn them back on.", ["SIRISOS_BACKUPS"], "/status")]
    found = service.backups()
    if not found:
        return [_item("backups", "Nightly backups", "SirisOS", "off", "None yet: the first runs tonight.", link="/status")]
    if not _recent(found[0]["created"], 2):
        return [_item("backups", "Nightly backups", "SirisOS", "problem", f"The newest is from {found[0]['created'][:10]}.",
                      "Check the backup folder is writable and has space (System status shows the last error).", ["SIRISOS_BACKUP_PATH"], "/status")]
    return [_item("backups", "Nightly backups", "SirisOS", "on", f"{len(found)} kept; the newest from {found[0]['created'][:10]}.", link="/status")]


def service_key() -> list[dict[str, Any]]:
    from app.service_key import service_key as configured

    raw = os.getenv("SIRISOS_SERVICE_KEY", "").strip()
    if configured():
        return [_item("service-key", "SirisAI's key into SirisOS", "SirisOS", "on", "SirisAI can use the engineering library and your career record.")]
    if raw:
        return [_item("service-key", "SirisAI's key into SirisOS", "SirisOS", "problem", "It's shorter than 24 characters, so SirisOS ignores it.",
                      "Make a longer one (openssl rand -hex 24) and set the same value on both sides.", ["SIRISOS_SERVICE_KEY", "SIRISAI_SIRISOS_SERVICE_KEY"])]
    return [_item("service-key", "SirisAI's key into SirisOS", "SirisOS", "off", "SirisAI can't use the engineering tools or read your CPD.",
                  "Make a key (openssl rand -hex 24) and set it in both.", ["SIRISOS_SERVICE_KEY", "SIRISAI_SIRISOS_SERVICE_KEY"])]


def terminal() -> list[dict[str, Any]]:
    from app.terminal import service

    if not service.enabled():
        return [_item("terminal", "Terminal", "SirisOS", "off", "No home machines to open a shell on.",
                      "List them, then add SirisOS's key (make terminal-key) to each machine's authorized_keys.", ["SIRISOS_TERMINAL_HOSTS"], "/terminal")]
    tf = service.two_factor()
    hosts = len(service.hosts())
    if tf.get("broken"):
        return [_item("terminal", "Terminal", "SirisOS", "problem", "Two-factor can't be read (the secret key changed).", "Set up 2FA again on the Terminal page.", link="/terminal")]
    if not tf.get("set_up"):
        return [_item("terminal", "Terminal", "SirisOS", "problem", f"{hosts} machine{'s' if hosts != 1 else ''} listed, but 2FA isn't set up, so it stays locked.",
                      "Set up 2FA on the Terminal page with your authenticator app.", link="/terminal")]
    return [_item("terminal", "Terminal", "SirisOS", "on", f"{hosts} machine{'s' if hosts != 1 else ''}, behind 2FA.", link="/terminal")]


def career() -> list[dict[str, Any]]:
    from app.career import store

    doc = store.load()
    if not doc.cpd.records:
        return [_item("cpd", "CPD from Engineers Australia", "You", "off", "No CPD imported, so the 150-hour totals and pacing are empty.",
                      "In the Engineers Australia portal, export your CPD record; then Career → CPD → Import.", link="/career?view=cpd")]
    last = doc.cpd.imports[0].at[:10] if doc.cpd.imports else None
    return [_item("cpd", "CPD from Engineers Australia", "You", "on", f"{len(doc.cpd.records)} activities{f', imported {last}' if last else ''}.", link="/career?view=cpd")]


async def apps(hub: Hub) -> list[dict[str, Any]]:
    out = []
    try:
        listed = await hub.apps()
    except Exception:  # noqa: BLE001
        return []
    prefixes = {c.id: c.env_prefix for c in hub.connectors}
    for a in listed:
        if a.get("id") in ("sirisai", "second-brain"):  # SirisAI has its own check
            continue
        state = (a.get("status") or {}).get("state")
        if state == "unconfigured":
            prefix = prefixes.get(a["id"]) or a["id"].upper()
            out.append(_item(f"app-{a['id']}", a["name"], "Apps", "off", "Not set up.", "Set its address in SirisOS's .env.", [f"{prefix}_URL"]))
        elif state in ("down", "degraded"):
            out.append(_item(f"app-{a['id']}", a["name"], "Apps", "problem", (a.get("status") or {}).get("detail") or "Not answering.", "Check it's running on the server."))
        else:
            out.append(_item(f"app-{a['id']}", a["name"], "Apps", "on", "Answering."))
    return out


def security() -> list[dict[str, Any]]:
    from app.security import service

    worst = [c for c in service.checks() if c["level"] != "info"]
    if not worst:
        return [_item("security", "Security settings", "SirisOS", "on", "Nothing to fix.", link="/security")]
    return [_item("security", "Security settings", "SirisOS", "problem", "; ".join(c["title"] for c in worst), worst[0]["fix"], link="/security")]


async def checklist(hub: Hub) -> dict[str, Any]:
    async def run(fn: Callable[[], Awaitable[list[dict[str, Any]]] | list[dict[str, Any]]], name: str) -> list[dict[str, Any]]:
        try:
            result = fn()
            if asyncio.iscoroutine(result):
                result = await asyncio.wait_for(result, 30)
            return result  # type: ignore[return-value]
        except Exception as exc:  # noqa: BLE001 - one check never stops the rest
            return [_item(name, name.replace("-", " ").capitalize(), "SirisOS", "problem", f"The check itself failed: {type(exc).__name__}")]

    groups = await asyncio.gather(
        run(lambda: sirisai(hub), "sirisai"), run(lambda: home(hub), "home"), run(lambda: health(hub), "health"),
        run(push, "push"), run(career, "cpd"), run(backups, "backups"), run(service_key, "service-key"),
        run(terminal, "terminal"), run(security, "security"), run(lambda: apps(hub), "apps"),
    )
    items = [i for g in groups for i in g]
    counts = {s: sum(i["state"] == s for i in items) for s in ("on", "off", "problem")}
    return {"items": items, "counts": counts, "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
