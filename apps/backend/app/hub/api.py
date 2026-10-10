"""Hub API (ADR 106): app tiles and widgets, plus thin proxies to SirisAI
(the assistant) and the Second Brain it serves, so the PWA only ever talks
to SirisOS and no app credential reaches a device."""

from __future__ import annotations

from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from app.auth import require_user
from app.hub.connectors.sirisai import SirisAIConnector
from app.hub.guest import guest_mode, hide_personal
from app.hub.service import Hub, get_hub, make_client, shared_client

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_user)])


@router.get("/hub/apps", tags=["hub"])
async def list_apps(
    widgets: bool = Query(False, description="Include each app's widget."),
    fresh: bool = Query(False, description="Bypass the short status cache."),
    hub: Hub = Depends(get_hub),
) -> dict[str, Any]:
    apps = await hub.apps(fresh=fresh, with_widgets=widgets)
    guest = widgets and await guest_mode(hub)
    return {"apps": hide_personal(apps) if guest else apps, "guest_mode": guest}


@router.get("/hub/apps/{app_id}", tags=["hub"])
async def get_app(app_id: str, fresh: bool = False, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    connector = hub.get(app_id)
    if connector is None:
        raise HTTPException(status_code=404, detail="Unknown app.")
    return await hub.app(connector, fresh=fresh, with_widget=True)


@router.get("/hub/widgets", tags=["hub"])
async def list_widgets(fresh: bool = False, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    apps = await hub.apps(fresh=fresh, with_widgets=True)
    guest = await guest_mode(hub)
    if guest:
        apps = hide_personal(apps)
    return {
        "guest_mode": guest,
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
        response = await shared_client().request(
            method, f"{connector.base_url}{path}", headers=connector.headers(), timeout=60.0, **kwargs
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"SirisAI unreachable: {type(exc).__name__}") from exc
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        status = 502 if response.status_code in (401, 403) else response.status_code
        # A structured detail (e.g. a protocol's preview with its 409) is kept as-is.
        raise HTTPException(status_code=status, detail=detail if isinstance(detail, dict) else f"SirisAI: {detail}")
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


async def _stream(
    connector: SirisAIConnector,
    path: str,
    body: dict[str, Any],
    *,
    files: dict[str, Any] | None = None,
    media_type: str = "text/event-stream",
) -> StreamingResponse:
    client = make_client(timeout=httpx.Timeout(10.0, read=None))
    # JSON for chat; multipart form fields (plus an optional recording) for voice.
    payload: dict[str, Any] = {"data": body, "files": files} if files is not None else {"json": body}
    try:
        upstream = await client.send(
            client.build_request("POST", f"{connector.base_url}{path}", headers=connector.headers(), **payload),
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
        media_type=media_type,
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


@router.get("/assistant/voice", tags=["assistant"])
async def voice_status(connector: SirisAIConnector = Depends(_sirisai)) -> dict[str, bool]:
    """Whether SirisAI can hear (speech-to-text) and speak (text-to-speech)."""
    status = await _forward(connector, "GET", "/siris/status") or {}
    enabled = lambda key: bool(status.get(key)) and status.get(key) != "none"  # noqa: E731
    return {"stt": enabled("stt_provider"), "tts": enabled("tts_provider")}


MAX_RECORDING_BYTES = 10 * 1024 * 1024


@router.post("/assistant/voice/converse", tags=["assistant"])
async def voice_converse(
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
    conversation_id: str | None = Form(None),
    synthesize: bool = Form(True),
    connector: SirisAIConnector = Depends(_sirisai),
) -> StreamingResponse:
    """SirisAI's POST /siris/voice/converse (one spoken turn), relayed as-is:
    newline-delimited JSON with the transcript, then each reply sentence with
    its audio, then a final event. It's the same conversation store as chat,
    so spoken turns feed the Second Brain's nightly dream too."""
    if file is None and not (text or "").strip():
        raise HTTPException(status_code=422, detail="Send a recording as 'file' or text as 'text'.")
    form = {"synthesize": "true" if synthesize else "false"}
    if text:
        form["text"] = text
    if conversation_id:
        form["conversation_id"] = conversation_id
    files = None
    if file is not None:
        audio = await file.read(MAX_RECORDING_BYTES + 1)
        if len(audio) > MAX_RECORDING_BYTES:
            raise HTTPException(status_code=413, detail="Recording is too long.")
        files = {"file": (file.filename or "sirisos.wav", audio, file.content_type or "audio/wav")}
    return await _stream(connector, "/siris/voice/converse", form, files=files or {}, media_type="application/x-ndjson")


@router.get("/assistant/hud", tags=["assistant"])
async def hud(connector: SirisAIConnector = Depends(_sirisai)) -> Any:
    return await _forward(connector, "GET", "/siris/hud/summary")


# -- SirisAI hub contract v1 (ADR 110) -----------------------------------------

# Names go into SirisAI paths: keep them to plain identifiers.
SafeName = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{1,60}$")]


@router.get("/assistant/info", tags=["assistant"])
async def assistant_info(connector: SirisAIConnector = Depends(_sirisai)) -> Any:
    """Who SirisAI thinks is asking, whether guest mode is on, and which of
    its integrations are configured -- what the PWA shows and hides by."""
    return await _forward(connector, "GET", "/siris/hub/v1")


@router.get("/assistant/widgets", tags=["assistant"])
async def assistant_widgets(connector: SirisAIConnector = Depends(_sirisai)) -> Any:
    """Car, parcels, power, protocols (and the last run, for undo), cameras and
    what SirisAI did on its own today."""
    return await _forward(connector, "GET", "/siris/hub/v1/widgets")


@router.get("/assistant/protocols/{name}", tags=["assistant"])
async def protocol_preview(name: SafeName, connector: SirisAIConnector = Depends(_sirisai)) -> Any:
    """What running the protocol would do right now, step by step."""
    return await _forward(connector, "GET", f"/siris/hub/v1/protocols/{name}")


class ProtocolRun(BaseModel):
    confirmed: bool = False


@router.post("/assistant/protocols/undo", tags=["assistant"])
async def protocol_undo(body: ProtocolRun, connector: SirisAIConnector = Depends(_sirisai)) -> Any:
    return await _forward(connector, "POST", "/siris/hub/v1/protocols/undo", json=body.model_dump())


@router.post("/assistant/protocols/{name}/run", tags=["assistant"])
async def protocol_run(name: SafeName, body: ProtocolRun, connector: SirisAIConnector = Depends(_sirisai)) -> Any:
    """Runs only with {"confirmed": true}: protocols change locks, covers and modes."""
    return await _forward(connector, "POST", f"/siris/hub/v1/protocols/{name}/run", json=body.model_dump())


class CameraQuestion(BaseModel):
    question: str | None = Field(default=None, max_length=300)


@router.post("/assistant/cameras/{camera}/look", tags=["assistant"])
async def camera_look(camera: SafeName, body: CameraQuestion, connector: SirisAIConnector = Depends(_sirisai)) -> Any:
    """SirisAI's vision model describes the camera's latest frame."""
    return await _forward(connector, "POST", f"/siris/hub/v1/cameras/{camera}/look", json=body.model_dump(exclude_none=True))


@router.get("/assistant/cameras/{camera}/latest.jpg", tags=["assistant"])
async def camera_frame(camera: SafeName, connector: SirisAIConnector = Depends(_sirisai)) -> Response:
    """The camera's latest frame, through SirisAI (which proxies Frigate), so
    neither Frigate nor the SirisAI key is exposed to the browser."""
    try:
        upstream = await shared_client().get(f"{connector.base_url}/siris/cameras/{camera}/latest.jpg", headers=connector.headers(),
                                             params={"height": 480}, timeout=15.0)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"SirisAI unreachable: {type(exc).__name__}") from exc
    if upstream.status_code >= 400:
        raise HTTPException(status_code=404 if upstream.status_code == 404 else 502, detail=f"No frame from {camera}")
    return Response(content=upstream.content, media_type=upstream.headers.get("content-type", "image/jpeg"),
                    headers={"Cache-Control": "no-store"})


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


class BrainPair(BaseModel):
    a: str = Field(min_length=1, max_length=200)
    b: str = Field(min_length=1, max_length=200)


@router.post("/brain/link", tags=["brain"])
async def brain_link(pair: BrainPair, connector: SirisAIConnector = Depends(_sirisai)) -> Any:
    """Accept a "could be linked" suggestion: the two notes are linked both ways."""
    return await _forward(connector, "POST", "/siris/brain/link", json=pair.model_dump())


@router.post("/brain/not-related", tags=["brain"])
async def brain_not_related(pair: BrainPair, connector: SirisAIConnector = Depends(_sirisai)) -> Any:
    """Dismiss a "could be linked" suggestion so it isn't suggested again."""
    return await _forward(connector, "POST", "/siris/brain/not-related", json=pair.model_dump())


@router.post("/brain/unlink", tags=["brain"])
async def brain_unlink(pair: BrainPair, connector: SirisAIConnector = Depends(_sirisai)) -> Any:
    """Disconnect two notes both ways; nothing automatic links them again."""
    return await _forward(connector, "POST", "/siris/brain/unlink", json=pair.model_dump())


@router.post("/brain/autolink", tags=["brain"])
async def brain_autolink(connector: SirisAIConnector = Depends(_sirisai)) -> Any:
    """Link the pairs the brain is confident about now, instead of at the nightly tidy."""
    return await _forward(connector, "POST", "/siris/brain/autolink")


@router.get("/brain/note", tags=["brain"])
async def brain_note(
    title: str = Query(min_length=1, max_length=200),
    connector: SirisAIConnector = Depends(_sirisai),
) -> Any:
    """One note with its links and backlinks, to review or unlink its connections."""
    return await _forward(connector, "GET", "/siris/brain/note", params={"title": title})


@router.get("/brain/insights", tags=["brain"])
async def brain_insights(
    days: int = Query(30, ge=7, le=365),
    connector: SirisAIConnector = Depends(_sirisai),
) -> Any:
    """How the Second Brain is growing and what needs attention, worked out by the vault's engine."""
    return await _forward(connector, "GET", "/siris/brain/insights", params={"days": days})


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
