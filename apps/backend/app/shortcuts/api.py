"""Apple Shortcuts and Siri.

Managed while signed in:
    GET    /api/v1/shortcuts/keys            the keys (never the secrets)
    POST   /api/v1/shortcuts/keys            {label, scopes}: a new key, shown once
    DELETE /api/v1/shortcuts/keys/{id}       revoke

Used by a Shortcut, with `Authorization: Bearer sk_…`, answering plain text
for "Show Result" or "Speak Text":
    POST /api/v1/shortcuts/capture           the body (text or JSON {text, url}) into the Second Brain inbox
    POST /api/v1/shortcuts/ask               the body as a question for SirisAI
    GET  /api/v1/shortcuts/today             today's brief, read aloud
    POST /api/v1/shortcuts/protocols/{name}  run a SirisAI protocol (Wind Down, Lockdown…)
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Request
from fastapi.responses import PlainTextResponse

from app.auth import require_user
from app.brief.service import brief_service
from app.hub.connectors.sirisai import SirisAIConnector
from app.hub.service import Hub, get_hub, shared_client
from app.shortcuts import keys

router = APIRouter(prefix="/api/v1/shortcuts", tags=["shortcuts"])


@router.get("/keys", dependencies=[Depends(require_user)])
def list_keys() -> dict[str, Any]:
    return {"keys": [keys.public(k) for k in keys.load()], "scopes": list(keys.SCOPES)}


@router.post("/keys", dependencies=[Depends(require_user)])
def new_key(body: keys.NewKey) -> dict[str, Any]:
    key, secret = keys.create(body.label, list(body.scopes))
    return {**keys.public(key), "secret": secret}


@router.delete("/keys/{key_id}", dependencies=[Depends(require_user)])
def revoke_key(key_id: str) -> dict[str, Any]:
    if not keys.revoke(key_id):
        raise HTTPException(status_code=404, detail="No such key.")
    return {"revoked": True}


def _sirisai(hub: Hub) -> SirisAIConnector:
    connector = hub.get("sirisai")
    if not isinstance(connector, SirisAIConnector) or not connector.configured:
        raise HTTPException(status_code=503, detail="SirisAI isn't connected to SirisOS.")
    return connector


async def _text(request: Request) -> tuple[str, str]:
    """The body as (text, url): plain text, or JSON with text/url (Shortcuts sends either)."""
    raw = (await request.body()).decode("utf-8", errors="replace").strip()
    if raw.startswith("{"):
        try:
            body = json.loads(raw)
            return str(body.get("text") or body.get("prompt") or "").strip(), str(body.get("url") or "").strip()
        except (ValueError, AttributeError):
            pass
    return raw, ""


async def _post(connector: SirisAIConnector, path: str, **kwargs: Any) -> httpx.Response:
    try:
        response = await shared_client().post(f"{connector.base_url}{path}", headers=connector.headers(), timeout=90.0, **kwargs)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"SirisAI unreachable: {type(exc).__name__}") from exc
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"SirisAI said {response.status_code}.")
    return response


@router.post("/capture", response_class=PlainTextResponse, dependencies=[Depends(keys.requires("capture"))])
async def capture(request: Request, hub: Hub = Depends(get_hub)) -> str:
    text, url = await _text(request)
    if not text and not url:
        raise HTTPException(status_code=422, detail="Send something to capture.")
    if not url and text.startswith(("http://", "https://")) and " " not in text:
        text, url = "", text
    result = (await _post(_sirisai(hub), "/siris/brain/capture", json={"text": text, "url": url, "tags": ["shortcut"]})).json()
    return f"Saved to your Second Brain as “{result.get('title', 'a capture')}”."


@router.post("/ask", response_class=PlainTextResponse, dependencies=[Depends(keys.requires("ask"))])
async def ask(request: Request, hub: Hub = Depends(get_hub)) -> PlainTextResponse:
    text, _ = await _text(request)
    if not text:
        raise HTTPException(status_code=422, detail="Send a question.")
    response = await _post(_sirisai(hub), "/siris/ask", json={"prompt": text})
    return PlainTextResponse(response.text, headers={k: v for k, v in response.headers.items() if k.lower() == "x-conversation-id"})


@router.get("/today", response_class=PlainTextResponse)
async def today(hub: Hub = Depends(get_hub), _: keys.Key = Depends(keys.requires("today"))) -> str:
    brief = await brief_service.build(hub, os.getenv("SIRISOS_ADMIN_USERNAME", "brad"))
    lines = [f"{brief['greeting'].split(',')[0]}."] + list(brief.get("headline") or [])
    changes = (brief.get("changes") or {}).get("lines") or []
    if changes:
        lines.append(f"Since {brief['changes']['label']}: " + " ".join(changes[:3]))
    return " ".join(lines)


@router.post("/protocols/{name}", response_class=PlainTextResponse, dependencies=[Depends(keys.requires("protocols"))])
async def run_protocol(name: str = Path(pattern=r"^[A-Za-z0-9_-]{1,40}$"), hub: Hub = Depends(get_hub)) -> str:
    """Runs straight away: tapping a Shortcut you set up is the confirmation."""
    result = (await _post(_sirisai(hub), f"/siris/hub/v1/protocols/{name}/run", json={"confirmed": True})).json()
    title = name.replace("_", " ").replace("-", " ").capitalize()
    ran, failed = result.get("ran") or [], result.get("failed") or []
    text = f"{title} done: {len(ran)} step{'s' if len(ran) != 1 else ''}." if ran else f"{title}: nothing needed doing."
    if failed:
        text += f" Couldn't {', '.join(failed[:3])}."
    if result.get("can_undo"):
        text += " You can undo it in SirisOS."
    return text
