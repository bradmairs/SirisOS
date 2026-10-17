"""Check a live SirisOS end to end, from inside its container:

    make verify                                   # everything
    make verify EA=data/app/ea-export.csv         # ...and try an Engineers Australia export
    make verify PUSH=1                            # ...and send every device a test notification

Each check prints ✓ (fine), ! (works, but worth a look) or ✗ (broken), with
what it found. Exit status is 1 when anything is ✗. Nothing is changed: the
EA export is parsed but not imported, and the brief isn't kept.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

ICON = {"ok": "✓", "warn": "!", "fail": "✗", "skip": "·"}


@dataclass
class Result:
    name: str
    state: str  # ok | warn | fail | skip
    detail: str = ""


async def _guard(name: str, check: Callable[[], Awaitable[Result | list[Result]]]) -> list[Result]:
    try:
        found = await asyncio.wait_for(check(), 60)
    except Exception as exc:  # noqa: BLE001 - one check never stops the rest
        return [Result(name, "fail", f"{type(exc).__name__}: {exc}"[:300])]
    return found if isinstance(found, list) else [found]


async def apps(hub) -> list[Result]:
    out = []
    for app in await hub.apps(fresh=True, with_widgets=True):
        state = app["status"]["state"]
        if state == "unconfigured":
            out.append(Result(f"App: {app['name']}", "skip", "not set up"))
            continue
        widget = app.get("widget")
        problem = widget.get("error") if isinstance(widget, dict) and "error" in widget else ""
        detail = " · ".join(x for x in [app["status"].get("version") or "", f"{app['status'].get('latency_ms')} ms", app["status"].get("detail") or "", f"widget: {problem}" if problem else ""] if x)
        out.append(Result(f"App: {app['name']}", {"ok": "warn" if problem else "ok", "degraded": "warn"}.get(state, "fail"), detail))
    return out


async def sirisai(hub) -> list[Result]:
    from app.hub.connectors.sirisai import SirisAIConnector
    from app.hub.service import shared_client

    connector = hub.get("sirisai")
    if not isinstance(connector, SirisAIConnector) or not connector.configured:
        return [Result("SirisAI", "skip", "SIRISAI_URL / SIRISAI_API_KEY not set")]
    client, base, headers = shared_client(), connector.base_url, connector.headers()

    async def get(path: str, **params: Any) -> httpx.Response:
        return await client.get(f"{base}{path}", headers=headers, params=params, timeout=30.0)

    out: list[Result] = []
    info = await get("/siris/hub/v1")
    if info.status_code == 200:
        body = info.json()
        features = [k for k, v in (body.get("features") or {}).items() if v]
        out.append(Result("SirisAI hub contract", "ok", f"user {body.get('user')}, guest mode {'on' if body.get('guest_mode') else 'off'}, features: {', '.join(features) or 'none'}"))
    else:
        out.append(Result("SirisAI hub contract", "fail", f"HTTP {info.status_code}: SirisAI is older than the hub contract (ADR 110)"))
    today = date.today()
    cal = await get("/siris/hub/v1/calendar", start=today.isoformat(), end=(today + timedelta(days=7)).isoformat())
    if cal.status_code == 404:
        out.append(Result("Calendar (next 7 days)", "fail", "SirisAI is older than 1.21: update it for the week view and CPD from calendar"))
    elif cal.status_code == 200:
        body = cal.json()
        if body.get("guest_mode"):
            out.append(Result("Calendar (next 7 days)", "warn", "guest mode is on, so it's hidden"))
        elif body.get("unavailable"):
            out.append(Result("Calendar (next 7 days)", "warn", "no calendar connected in SirisAI, or every calendar failed"))
        else:
            events = body.get("events") or []
            calendars = sorted({str(e.get("calendar")) for e in events if e.get("calendar")})
            out.append(Result("Calendar (next 7 days)", "ok", f"{len(events)} events from {', '.join(calendars) or 'no named calendars'}"))
    else:
        out.append(Result("Calendar (next 7 days)", "fail", f"HTTP {cal.status_code}"))
    fc = await get("/siris/hub/v1/forecast", days=7)
    if fc.status_code == 200 and not fc.json().get("unavailable"):
        out.append(Result("Forecast", "ok", f"{len(fc.json().get('days') or [])} days"))
    else:
        out.append(Result("Forecast", "warn", "no forecast (set SIRISAI_WEATHER_LATITUDE/LONGITUDE in SirisAI)" if fc.status_code == 200 else f"HTTP {fc.status_code}"))
    search = await get("/siris/brain/search", q="project", limit=3)
    out.append(Result("Siris search", "ok" if search.status_code == 200 else "fail",
                      f"{len(search.json())} results for 'project'" if search.status_code == 200 else f"HTTP {search.status_code}"))
    insights = await get("/siris/brain/insights", days=7)
    if insights.status_code == 200:
        s = insights.json().get("summary") or {}
        out.append(Result("Siris insights", "ok", f"{s.get('notes', '?')} notes, {s.get('inbox', 0)} in the inbox"))
    else:
        out.append(Result("Siris insights", "fail", f"HTTP {insights.status_code}"))
    return out


async def service_key(api) -> Result:
    from app.service_key import service_key as configured

    key = configured()
    if key is None:
        raw = os.getenv("SIRISOS_SERVICE_KEY", "").strip()
        return Result("SirisAI's key into SirisOS", "warn" if raw else "skip", "set but shorter than 24 characters, so ignored" if raw else "SIRISOS_SERVICE_KEY not set (SirisAI can't use the engineering tools)")
    auth = {"Authorization": f"Bearer {key}"}
    allowed = await api.get("/api/v1/engineering/calculators", headers=auth)
    refused = await api.post("/api/v1/projects", headers=auth, json={"name": "verify"})
    if allowed.status_code == 200 and refused.status_code == 403:
        return Result("SirisAI's key into SirisOS", "ok", "opens the calculators, refused creating a project")
    return Result("SirisAI's key into SirisOS", "fail", f"calculators {allowed.status_code} (want 200), create project {refused.status_code} (want 403)")


async def push(send_test: bool) -> list[Result]:
    from app.hub.service import shared_client
    from app.push import store, webpush

    subs = store.subscriptions()
    out = [Result("Phone notifications", "ok" if subs else "skip",
                  f"{len(subs)} device{'s' if len(subs) != 1 else ''}: {', '.join(s.label or '?' for s in subs)}" if subs else "no device has turned them on (Inbox → Notifications on this device)")]
    if send_test:
        for sub in subs:
            try:
                await webpush.send(shared_client(), sub.model_dump(), {"title": "SirisOS check", "body": "Notifications reach this device.", "url": "/", "tag": "verify"})
                out.append(Result(f"Test notification to {sub.label or 'a device'}", "ok", "sent"))
            except Exception as exc:  # noqa: BLE001
                out.append(Result(f"Test notification to {sub.label or 'a device'}", "fail", str(exc)[:200]))
    return out


async def security() -> list[Result]:
    from app.security import service

    found = service.checks()
    if not [c for c in found if c["level"] != "info"]:
        return [Result("Security settings", "ok", "nothing to fix" + (f" ({'; '.join(c['title'] for c in found)})" if found else ""))]
    return [Result(f"Security: {c['title']}", "fail" if c["level"] == "critical" else "warn", c["fix"]) for c in found if c["level"] != "info"]


async def brief(hub) -> Result:
    from app.brief.service import BriefService

    built = await BriefService().build(hub, os.getenv("SIRISOS_ADMIN_USERNAME", "brad"), fresh=True)
    missing = built.get("unavailable") or []
    return Result("Daily brief", "warn" if missing else "ok", f"{len(built.get('headline') or [])} headline lines" + (f"; couldn't reach: {', '.join(missing)}" if missing else ""))


async def ea_export(path: str) -> Result:
    from app.career import cpd, store

    raw = Path(path).read_bytes()
    records = cpd.parse(raw, path)
    doc, result = cpd.merge(store.load(), records, path, save_result=False)
    summary = cpd.summary(doc)
    guessed = sum(1 for r in records if r.basis == "guess")
    return Result("Engineers Australia export", "warn" if guessed else "ok",
                  f"{len(records)} activities ({result.added} new, {result.updated} changed); {summary['total']:g} of {summary['required']} hours in 3 years"
                  + (f"; {guessed} categories guessed from titles" if guessed else "") + " (not saved)")


async def run(args: argparse.Namespace, api: httpx.AsyncClient) -> list[Result]:
    from app.hub.service import get_hub

    hub = get_hub()
    results: list[Result] = []
    results += await _guard("Apps", lambda: apps(hub))
    results += await _guard("SirisAI", lambda: sirisai(hub))
    results += await _guard("Service key", lambda: service_key(api))
    results += await _guard("Notifications", lambda: push(args.push))
    results += await _guard("Security", security)
    results += await _guard("Daily brief", lambda: brief(hub))
    if args.ea:
        results += await _guard("Engineers Australia export", lambda: ea_export(args.ea))
    return results


def report(results: list[Result]) -> tuple[str, bool]:
    width = min(30, max((len(r.name) for r in results), default=0))
    lines = []
    for r in results:
        if len(r.name) > width:  # a long name gets the detail on its own line
            lines += [f"{ICON[r.state]} {r.name}", f"  {'':<{width}}  {r.detail}".rstrip()]
        else:
            lines.append(f"{ICON[r.state]} {r.name:<{width}}  {r.detail}".rstrip())
    counts = {s: sum(1 for r in results if r.state == s) for s in ICON}
    lines.append(f"\n{counts['ok']} fine, {counts['warn']} worth a look, {counts['fail']} broken, {counts['skip']} not set up.")
    return "\n".join(lines), counts["fail"] == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ea", help="an Engineers Australia CPD export to try (parsed, not saved)")
    parser.add_argument("--push", action="store_true", help="send every subscribed device a test notification")
    parser.add_argument("--api", default=os.getenv("SIRISOS_VERIFY_API", "http://127.0.0.1:8000"), help="this SirisOS API (default: inside the container)")
    args = parser.parse_args(argv)

    async def go() -> list[Result]:
        async with httpx.AsyncClient(base_url=args.api, timeout=20.0) as api:
            return await run(args, api)

    text, ok = report(asyncio.run(go()))
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
