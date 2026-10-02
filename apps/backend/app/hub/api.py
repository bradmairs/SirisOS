"""Hub API (ADR 106): app tiles and widgets, plus thin proxies to SirisAI
(the assistant) and the Second Brain it serves, so the PWA only ever talks
to SirisOS and no app credential reaches a device."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.auth import require_user
from app.hub.connectors.sirisai import SirisAIConnector
from app.hub.service import Hub, get_hub, make_client

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_user)])


@router.get("/hub/apps", tags=["hub"])
async def list_apps(
    widgets: bool = Query(False, description="Include each app's widget."),
    fresh: bool = Query(False, description="Bypass the short status cache."),
    hub: Hub = Depends(get_hub),
) -> dict[str, Any]:
    return {"apps": await hub.apps(fresh=fresh, with_widgets=widgets)}


@router.get("/hub/apps/{app_id}", tags=["hub"])
async def get_app(app_id: str, fresh: bool = False, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    connector = hub.get(app_id)
    if connector is None:
        raise HTTPException(status_code=404, detail="Unknown app.")
    async with make_client() as client:
        return await hub.app(connector, client, fresh=fresh, with_widget=True)


@router.get("/hub/widgets", tags=["hub"])
async def list_widgets(fresh: bool = False, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    apps = await hub.apps(fresh=fresh, with_widgets=True)
    return {
        "widgets": [
            {"app_id": a["id"], "app_name": a["name"], "icon": a["icon"], "launch_url": a["launch_url"], **a["widget"]}
            for a in apps
            if a.get("widget")
        ]
    }


# -- SirisAI / Second Brain proxies -----------------------------------------


def _sirisai(hub: Hub = Depends(get_hub)) -> SirisAIConnector:
    connector = hub.get("sirisai")
    if not isinstance(connector, SirisAIConnector) or not connector.configured:
        raise HTTPException(status_code=503, detail="SirisAI is not configured. Set SIRISAI_URL and SIRISAI_API_KEY.")
    return connector


async def _forward(connector: SirisAIConnector, method: str, path: str, *, raw: bool = False, **kwargs: Any) -> Any:
    try:
        async with make_client(timeout=60.0) as client:
            response = await client.request(method, f"{connector.base_url}{path}", headers=connector.headers(), **kwargs)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"SirisAI unreachable: {type(exc).__name__}") from exc
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        status = 502 if response.status_code in (401, 403) else response.status_code
        raise HTTPException(status_code=status, detail=f"SirisAI: {detail}")
    if raw:
        return response.text
    if response.status_code == 204 or not response.content:
        return None
    return response.json()


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    conversation_id: str | None = None
    images: list[str] | None = None


class ConfirmRequest(BaseModel):
    conversation_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    # Continue a planner turn past the confirmed step (SirisAI ConfirmToolRequest).
    use_planner: bool = False


async def _stream(connector: SirisAIConnector, path: str, body: dict[str, Any]) -> StreamingResponse:
    client = make_client(timeout=httpx.Timeout(10.0, read=None))
    try:
        upstream = await client.send(
            client.build_request("POST", f"{connector.base_url}{path}", headers=connector.headers(), json=body),
            stream=True,
        )
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(status_code=502, detail=f"SirisAI unreachable: {type(exc).__name__}") from exc
    if upstream.status_code >= 400:
        text = (await upstream.aread()).decode(errors="replace")
        await upstream.aclose()
        await client.aclose()
        raise HTTPException(status_code=502, detail=f"SirisAI: HTTP {upstream.status_code} {text[:300]}")

    async def relay():
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        relay(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/assistant/chat/stream", tags=["assistant"])
async def chat_stream(request: ChatRequest, connector: SirisAIConnector = Depends(_sirisai)) -> StreamingResponse:
    """SirisAI's POST /siris/chat/stream, relayed as-is (Server-Sent Events)."""
    return await _stream(connector, "/siris/chat/stream", request.model_dump(exclude_none=True))


@router.post("/assistant/chat/confirm/stream", tags=["assistant"])
async def confirm_stream(request: ConfirmRequest, connector: SirisAIConnector = Depends(_sirisai)) -> StreamingResponse:
    return await _stream(connector, "/siris/chat/confirm/stream", request.model_dump())


@router.get("/assistant/conversations", tags=["assistant"])
async def conversations(limit: int = Query(20, ge=1, le=50), connector: SirisAIConnector = Depends(_sirisai)) -> Any:
    return await _forward(connector, "GET", "/siris/conversations", params={"limit": limit})


@router.get("/assistant/conversations/{conversation_id}", tags=["assistant"])
async def conversation(conversation_id: str, connector: SirisAIConnector = Depends(_sirisai)) -> Any:
    return await _forward(connector, "GET", f"/siris/conversations/{conversation_id}")


@router.get("/assistant/hud", tags=["assistant"])
async def hud(connector: SirisAIConnector = Depends(_sirisai)) -> Any:
    return await _forward(connector, "GET", "/siris/hud/summary")


@router.get("/brain/search", tags=["brain"])
async def brain_search(
    q: str = Query(min_length=1, max_length=500),
    limit: int = Query(8, ge=1, le=30),
    connector: SirisAIConnector = Depends(_sirisai),
) -> Any:
    return await _forward(connector, "GET", "/siris/brain/search", params={"q": q, "limit": limit})


@router.get("/brain/today", tags=["brain"])
async def brain_today(connector: SirisAIConnector = Depends(_sirisai)) -> Any:
    return await _forward(connector, "GET", "/siris/brain/today")


@router.get("/brain/map.html", tags=["brain"], response_class=HTMLResponse)
async def brain_map(connector: SirisAIConnector = Depends(_sirisai)) -> HTMLResponse:
    """The Second Brain's living mind map, drawn fresh from the vault by SirisAI.
    The PWA renders it in a sandboxed iframe, so it never sees the SirisAI key."""
    return HTMLResponse(await _forward(connector, "GET", "/siris/brain/map.html", raw=True))


class CaptureRequest(BaseModel):
    text: str = Field(default="", max_length=20000)
    url: str = Field(default="", max_length=2000)
    title: str = Field(default="", max_length=200)
    tags: list[str] = Field(default_factory=list, max_length=20)


@router.post("/brain/capture", tags=["brain"])
async def brain_capture(request: CaptureRequest, connector: SirisAIConnector = Depends(_sirisai)) -> Any:
    if not request.text.strip() and not request.url.strip():
        raise HTTPException(status_code=422, detail="Send some text, a url, or both.")
    return await _forward(connector, "POST", "/siris/brain/capture", json=request.model_dump())
