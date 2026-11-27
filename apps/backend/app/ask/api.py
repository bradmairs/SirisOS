"""Ask Siris (11.16). See service.py.

    GET    /api/v1/ask/key     signed in: whether there's a key
    POST   /api/v1/ask/key     signed in: a new key (shown once; the old one stops working)
    DELETE /api/v1/ask/key     signed in: turn it off
    POST   /api/v1/ask         with X-SirisOS-Key: JSON {text, conversation_id?, new?}
                               -> {say, conversation_id, link}
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.ask import service
from app.auth import require_user
from app.hub import sirisai_api
from app.hub.service import Hub, get_hub

router = APIRouter(prefix="/api/v1/ask", tags=["ask"])


@router.get("/key", dependencies=[Depends(require_user)])
def get_key() -> dict[str, Any]:
    return service.state()


@router.post("/key", dependencies=[Depends(require_user)])
def make_key() -> dict[str, Any]:
    """A new Ask key (11.16), shown once; the old one stops working."""
    return {"key": service.new_key(), "url": "/api/v1/ask"}


@router.delete("/key", dependencies=[Depends(require_user)])
def drop_key() -> dict[str, Any]:
    service.drop_key()
    return service.state()


@router.post("")
async def ask(request: Request, x_sirisos_key: str | None = Header(default=None), hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    """Ask Siris from a Shortcut (11.16), with the Ask key in X-SirisOS-Key. Never approves anything."""
    if not service.matches(x_sirisos_key):
        raise HTTPException(status_code=401, detail="That key isn't right: make a new one on SirisOS's Security page.")
    if not service.allow():
        raise HTTPException(status_code=429, detail="That's a lot of questions: try again in a while.")
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(status_code=422, detail="Send JSON {text}.") from None
    text = str((body or {}).get("text") or "").strip()[: service.MAX_CHARS] if isinstance(body, dict) else ""
    if not text:
        raise HTTPException(status_code=422, detail="Nothing to ask.")
    conv = None if body.get("new") else service.conversation(body.get("conversation_id"))
    payload: dict[str, Any] = {"prompt": text}
    if conv:
        payload["conversation_id"] = conv
    try:
        out = await sirisai_api.post(hub, "/siris/chat", json=payload, timeout=120.0) or {}
    except sirisai_api.SirisAIError as exc:
        raise HTTPException(status_code=502, detail=f"SirisAI isn't answering: {exc}") from None
    conv = out.get("conversation_id") or conv
    service.remember(conv)
    return {"say": service.say(out), "conversation_id": conv, "link": f"/assistant?c={conv}" if conv else "/assistant"}
