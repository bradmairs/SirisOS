"""Add to SirisOS (8.9). See service.py.

    GET    /api/v1/share/key        signed in: whether there's a key
    POST   /api/v1/share/key        signed in: a new key (shown once; the old one stops working)
    DELETE /api/v1/share/key        signed in: turn it off
    POST   /api/v1/share            with X-SirisOS-Key: JSON {text, task?} or a form with `file` (and `text`)
                                    -> {kind, say, link}
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.auth import require_user
from app.hub import sirisai_api
from app.hub.service import Hub, get_hub
from app.share import service
from app.tasks import service as tasks
from app.tasks import store as task_store

MAX_BYTES = 20_000_000

router = APIRouter(prefix="/api/v1/share", tags=["share"])


@router.get("/key", dependencies=[Depends(require_user)])
def get_key() -> dict[str, Any]:
    return service.state()


@router.post("/key", dependencies=[Depends(require_user)])
def make_key() -> dict[str, Any]:
    return {"key": service.new_key(), "url": "/api/v1/share"}


@router.delete("/key", dependencies=[Depends(require_user)])
def drop_key() -> dict[str, Any]:
    service.drop_key()
    return service.state()


async def _add_text(hub: Hub, text: str, as_task: bool) -> dict[str, Any]:
    kind = service.kind_of(text, as_task)
    if kind == "task":
        today = tasks.today()
        task = tasks.due_today_unless_said(tasks.parse(service.LEAD.sub("", text, count=1) or text, today), today)
        task.notes = (task.notes + "\n" if task.notes else "") + "Shared to SirisOS"
        tasks.add(task)
        when = "" if task.due == today.isoformat() else f", due {date.fromisoformat(task.due).strftime('%a %-d %b')}" if task.due else ""
        return {"kind": "task", "say": f"Added a task: {task.title}{when}.", "link": "/tasks"}
    body = {"url": text.strip()} if kind == "url" else {"text": text, "tags": ["shared"]}
    saved = await sirisai_api.post(hub, "/siris/brain/capture", json=body)
    title = (saved or {}).get("title")
    return {"kind": kind, "say": f"Saved to Siris{f': {title}' if title else ''}.", "link": "/brain"}


@router.post("")
async def share(request: Request, x_sirisos_key: str | None = Header(default=None), hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    if not service.matches(x_sirisos_key):
        raise HTTPException(status_code=401, detail="That key isn't right: make a new one on SirisOS's Security page.")
    if not service.allow():
        raise HTTPException(status_code=429, detail="That's a lot at once: try again in a while.")
    if int(request.headers.get("content-length") or 0) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="That's over 20 MB.")
    kind = request.headers.get("content-type", "")
    try:
        if kind.startswith("multipart/form-data"):
            form = await request.form()
            upload = form.get("file")
            text = str(form.get("text") or "").strip()
            if upload is not None and hasattr(upload, "read"):
                data = await upload.read()
                if len(data) > MAX_BYTES:
                    raise HTTPException(status_code=413, detail="That's over 20 MB.")
                if not data:
                    raise HTTPException(status_code=422, detail="The file was empty.")
                r = await sirisai_api.raw(hub, "POST", "/siris/documents", timeout=300.0,
                                          files={"file": (upload.filename or "shared", data, upload.content_type or "application/octet-stream")})
                if r.status_code >= 400:
                    raise HTTPException(status_code=502, detail=f"SirisAI couldn't take it ({r.status_code}).")
                doc = r.json() or {}
                things = doc.get("things") or []
                say = f"Filed: {doc.get('title') or upload.filename}" + (f" ({doc['kind']})" if doc.get("kind") else "")
                if things:
                    say += f", and added {', '.join(t['name'] for t in things[:3])} to Things you own"
                return {"kind": "document", "say": say + ".", "link": "/life"}
            if not text:
                raise HTTPException(status_code=422, detail="Nothing to add: share a photo, a PDF, a link or some text.")
            return await _add_text(hub, text, str(form.get("task") or "").lower() in ("1", "true", "yes"))
        body = await request.json()
    except ValueError:
        raise HTTPException(status_code=422, detail="Send JSON {text} or a form with a file.") from None
    except sirisai_api.SirisAIError as exc:
        raise HTTPException(status_code=502, detail=f"SirisAI isn't answering: {exc}") from None
    text = str((body or {}).get("text") or (body or {}).get("url") or "").strip()[:20000] if isinstance(body, dict) else ""
    if not text:
        raise HTTPException(status_code=422, detail="Nothing to add: share a photo, a PDF, a link or some text.")
    try:
        return await _add_text(hub, text, bool(body.get("task")))
    except sirisai_api.SirisAIError as exc:
        raise HTTPException(status_code=502, detail=f"SirisAI isn't answering: {exc}") from None
