"""Terminal API (2.8).

    GET    /api/v1/terminal              signed in: hosts, 2FA state, SirisOS's public key, live sessions, recent activity
    POST   /api/v1/terminal/2fa/setup    signed in + {password}: a new authenticator secret (QR code and link)
    POST   /api/v1/terminal/2fa/confirm  signed in + {code}: the first code turns 2FA on
    POST   /api/v1/terminal/2fa/off      signed in + {password, code}: turn 2FA off
    POST   /api/v1/terminal/unlock       signed in + {host, code}: a ticket for one terminal, good once for 30 s
    WS     /api/v1/terminal/ws?ticket=   the terminal itself
    GET    /api/v1/terminal/commands     shortcuts: built-in and saved one-tap commands (3.4)
    POST   /api/v1/terminal/commands     {name, command, host?}: save one
    DELETE /api/v1/terminal/commands/{id}
    POST   /api/v1/terminal/run          {ticket, command}: run a shortcut with a fresh unlock; its output comes back

Over the WebSocket the browser sends JSON text frames ({"type": "input",
"data"} and {"type": "resize", "cols", "rows"}) and gets the shell's output
as binary frames. A session closes after SIRISOS_TERMINAL_IDLE_MINUTES with
no typing (15) or SIRISOS_TERMINAL_MAX_MINUTES in all (120), and a new one
needs a new code.
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.auth import require_user
from app.security import api as security_api
from app.security import service as security
from app.terminal import commands, service, store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/terminal", tags=["terminal"])


class Password(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class Code(BaseModel):
    code: str = Field(min_length=6, max_length=12)


class TurnOff(Password):
    code: str = Field(min_length=6, max_length=12)


class Unlock(BaseModel):
    host: str = Field(min_length=1, max_length=32)
    code: str = Field(min_length=6, max_length=12)


def _not_enabled() -> HTTPException:
    return HTTPException(status_code=404, detail="The terminal is off. Set SIRISOS_TERMINAL_HOSTS on the server to turn it on.")


def _check_password(password: str, request: Request) -> None:
    from app.main import AUTH_PASSWORD

    client = security_api.client_of(request)
    wait = security.blocked_for(client)
    if wait:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again soon.", headers={"Retry-After": str(wait)})
    if not secrets.compare_digest(password, AUTH_PASSWORD):
        security.failed(client)
        store.audit("password-refused", client=client)
        raise HTTPException(status_code=401, detail="That isn't your SirisOS password.")
    security.succeeded(client)


def _check_code(code: str, client: str, what: str) -> None:
    wait = service.blocked_for(client)
    if wait:
        raise HTTPException(status_code=429, detail=f"Too many wrong codes. Try again in {max(1, wait // 60)} min.",
                            headers={"Retry-After": str(wait)})
    if not service.verify_code(code):
        service.failed(client)
        store.audit("code-refused", client=client, for_=what)
        raise HTTPException(status_code=401, detail="That code didn't work. Codes work once: wait for the next one.")
    service.succeeded(client)


@router.get("", dependencies=[Depends(require_user)])
def status() -> dict[str, Any]:
    on = service.enabled()
    return {
        "enabled": on,
        "hosts": [{"name": h.name, "target": h.target, "host_key": store.fingerprint(k) if (k := service.pinned_key(h.name)) else None}
                  for h in service.hosts()],
        "two_factor": service.two_factor(),
        "public_key": service.public_key() if on else None,
        "idle_minutes": service.idle_minutes(),
        "max_minutes": service.max_minutes(),
        "sessions": service.sessions(),
        "activity": store.recent_audit(12),
    }


@router.post("/2fa/setup")
def setup(body: Password, request: Request, user: str = Depends(require_user)) -> dict[str, Any]:
    if not service.enabled():
        raise _not_enabled()
    _check_password(body.password, request)
    try:
        started = service.begin_setup(user)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    import segno

    qr = segno.make(started["uri"], error="m").svg_inline(scale=5, dark="#000", light="#fff", border=2)
    store.audit("2fa-setup-started", client=security_api.client_of(request))
    return {**started, "qr_svg": qr}


@router.post("/2fa/confirm", dependencies=[Depends(require_user)])
def confirm(body: Code, request: Request) -> dict[str, Any]:
    client = security_api.client_of(request)
    wait = service.blocked_for(client)
    if wait:
        raise HTTPException(status_code=429, detail="Too many wrong codes. Try again soon.", headers={"Retry-After": str(wait)})
    if not service.confirm_setup(body.code):
        service.failed(client)
        raise HTTPException(status_code=401, detail="That code didn't match. Check the app shows SirisOS and try the next code.")
    service.succeeded(client)
    store.audit("2fa-on", client=client)
    return {"two_factor": service.two_factor()}


@router.post("/2fa/off", dependencies=[Depends(require_user)])
def turn_off(body: TurnOff, request: Request) -> dict[str, Any]:
    _check_password(body.password, request)
    client = security_api.client_of(request)
    _check_code(body.code, client, "2fa-off")
    service.turn_off()
    store.audit("2fa-off", client=client)
    return {"two_factor": service.two_factor()}


@router.post("/unlock", dependencies=[Depends(require_user)])
def unlock(body: Unlock, request: Request) -> dict[str, Any]:
    if not service.enabled():
        raise _not_enabled()
    host = service.find_host(body.host)
    if host is None:
        raise HTTPException(status_code=404, detail="No such host.")
    if not service.two_factor()["set_up"]:
        raise HTTPException(status_code=403, detail="Set up 2FA first.")
    client = security_api.client_of(request)
    _check_code(body.code, client, host.name)
    store.audit("unlocked", client=client, host=host.name)
    return {"ticket": service.new_ticket(host.name, client), "expires_in": service.TICKET_SECONDS}


# -- the terminal ------------------------------------------------------------------

def _same_origin(ws: WebSocket) -> bool:
    origin = ws.headers.get("origin")
    if not origin:
        return False
    return urlsplit(origin).netloc.lower() == (ws.headers.get("host") or "").lower()


async def _notify(host: str, client: str) -> None:
    """A phone notification for every terminal that opens, to every device with notifications on."""
    try:
        from app.hub.service import shared_client
        from app.push import store as push_store, webpush

        payload = {"title": "Terminal opened", "body": f"{host}, from {client}. Not you? Turn 2FA off on the Terminal page.",
                   "url": "/terminal", "tag": f"terminal-{int(time.time())}"}
        for sub in push_store.subscriptions():
            try:
                await webpush.send(shared_client(), sub.model_dump(), payload, urgency="high")
            except Exception:  # noqa: BLE001 - a notification never blocks the terminal
                pass
    except Exception as exc:  # noqa: BLE001
        logger.info("Terminal notification skipped: %s", exc)


async def _connect(host: service.Host):
    import asyncssh

    pinned = service.pinned_key(host.name)
    known = ([asyncssh.import_public_key(pinned)], [], []) if pinned else None
    conn = await asyncio.wait_for(asyncssh.connect(
        host.host, port=host.port, username=host.user, client_keys=[service.client_key()],
        known_hosts=known, agent_path=None, password=None, kbdint_auth=False, preferred_auth="publickey",
    ), timeout=15)
    if not pinned:
        key = conn.get_server_host_key()
        service.pin(host.name, key.export_public_key().decode().strip())
        store.audit("host-key-pinned", host=host.name, fingerprint=store.fingerprint(key.export_public_key().decode()))
    return conn


@router.websocket("/ws")
async def terminal(ws: WebSocket, ticket: str = "") -> None:
    if not _same_origin(ws):
        await ws.close(code=4403)
        return
    taken = service.take_ticket(ticket)
    host = service.find_host(taken[0]) if taken else None
    if not taken or host is None:
        await ws.close(code=4401)
        return
    client = taken[1]
    sid = service.open_session(host.name, client)
    if sid is None:
        await ws.close(code=4429)
        return
    await ws.accept()
    started = time.monotonic()
    store.audit("session-start", client=client, host=host.name, session=sid)
    asyncio.create_task(_notify(host.name, client))
    reason = "closed"
    conn = None
    try:
        try:
            conn = await _connect(host)
        except Exception as exc:  # noqa: BLE001 - say why in the terminal itself
            text = "The host's SSH key has changed, so SirisOS won't connect. If you expected that, run make terminal-forget-host NAME=" + host.name if "Host key is not trusted" in str(exc) else str(exc) or type(exc).__name__
            await ws.send_text(json.dumps({"type": "error", "message": f"Couldn't connect to {host.target}: {text}"}))
            reason = "connect-failed"
            return
        proc = await conn.create_process(term_type="xterm-256color", term_size=(80, 24), encoding=None)
        await ws.send_text(json.dumps({"type": "ready", "host": host.name, "target": host.target,
                                       "idle_minutes": service.idle_minutes(), "max_minutes": service.max_minutes()}))
        last_input = time.monotonic()

        async def pump_out() -> None:
            while True:
                data = await proc.stdout.read(65536)
                if not data:
                    return
                await ws.send_bytes(data)

        async def pump_in() -> None:
            nonlocal last_input
            while True:
                msg = json.loads(await ws.receive_text())
                if msg.get("type") == "input" and isinstance(msg.get("data"), str):
                    last_input = time.monotonic()
                    proc.stdin.write(msg["data"].encode())
                elif msg.get("type") == "resize":
                    cols, rows = int(msg.get("cols", 80)), int(msg.get("rows", 24))
                    proc.change_terminal_size(max(10, min(cols, 500)), max(4, min(rows, 200)))

        async def watchdog() -> str:
            while True:
                await asyncio.sleep(5)
                now = time.monotonic()
                if now - last_input > service.idle_minutes() * 60:
                    return "idle"
                if now - started > service.max_minutes() * 60:
                    return "time-limit"

        tasks = {asyncio.create_task(pump_out()): "shell-exit", asyncio.create_task(pump_in()): "closed",
                 asyncio.create_task(watchdog()): "watchdog"}
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
        first = next(iter(done))
        reason = tasks[first]
        if reason == "watchdog":
            reason = first.result()
        if reason in ("idle", "time-limit"):
            note = "no typing for a while" if reason == "idle" else "the time limit"
            try:
                await ws.send_text(json.dumps({"type": "ended", "reason": reason, "message": f"Session closed after {note}. Unlock again to carry on."}))
            except Exception:  # noqa: BLE001
                pass
    except WebSocketDisconnect:
        reason = "closed"
    finally:
        if conn is not None:
            conn.close()
        service.close_session(sid)
        store.audit("session-end", client=client, host=host.name, session=sid, reason=reason,
                    minutes=round((time.monotonic() - started) / 60, 1))
        try:
            await ws.close()
        except Exception:  # noqa: BLE001
            pass


# -- shortcuts (3.4) --------------------------------------------------------------


class NewCommand(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    command: str = Field(min_length=1, max_length=2000)
    host: str | None = Field(default=None, max_length=32)


class Run(BaseModel):
    ticket: str = Field(min_length=10, max_length=200)
    command: str = Field(min_length=1, max_length=40)


@router.get("/commands", dependencies=[Depends(require_user)])
def list_commands() -> dict[str, Any]:
    return {"commands": commands.all_commands(), "seconds": commands.seconds()}


@router.post("/commands", dependencies=[Depends(require_user)])
def add_command(body: NewCommand, request: Request) -> dict[str, Any]:
    if body.host and service.find_host(body.host) is None:
        raise HTTPException(status_code=404, detail="No such host.")
    try:
        made = commands.add(body.name, body.command, body.host)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    store.audit("shortcut-saved", client=security_api.client_of(request), name=made["name"])
    return made


@router.delete("/commands/{command_id}", dependencies=[Depends(require_user)])
def delete_command(command_id: str) -> dict[str, Any]:
    if command_id.startswith("builtin:") or not commands.remove(command_id):
        raise HTTPException(status_code=404, detail="No such shortcut.")
    return {"removed": True}


@router.post("/run", dependencies=[Depends(require_user)])
async def run_command(body: Run, request: Request) -> dict[str, Any]:
    """Run a shortcut on the host its ticket was unlocked for (the ticket works once)."""
    taken = service.take_ticket(body.ticket)
    if not taken:
        raise HTTPException(status_code=401, detail="That unlock expired. Enter a new code.")
    host = service.find_host(taken[0])
    found = commands.find(body.command)
    if host is None or found is None:
        raise HTTPException(status_code=404, detail="No such shortcut or host.")
    if found.get("host") and found["host"] != host.name:
        raise HTTPException(status_code=409, detail=f"“{found['name']}” runs on {found['host']}.")
    client = taken[1]
    store.audit("shortcut-run", client=client, host=host.name, name=found["name"])
    asyncio.create_task(_notify(host.name, client))
    started = time.monotonic()
    try:
        conn = await _connect(host)
    except Exception as exc:  # noqa: BLE001
        text = "The host's SSH key has changed, so SirisOS won't connect." if "Host key is not trusted" in str(exc) else str(exc) or type(exc).__name__
        raise HTTPException(status_code=502, detail=f"Couldn't connect to {host.target}: {text}") from None
    try:
        result = await asyncio.wait_for(conn.run(found["command"], check=False), timeout=commands.seconds())
        output, cut = commands.tail(f"{result.stdout or ''}{result.stderr or ''}")
        code = result.exit_status
        timed_out = False
    except asyncio.TimeoutError:
        output, cut, code, timed_out = f"Stopped after {commands.seconds()} seconds.", False, None, True
    finally:
        conn.close()
    store.audit("shortcut-done", host=host.name, name=found["name"], exit=code, seconds=round(time.monotonic() - started, 1))
    return {"name": found["name"], "host": host.name, "command": found["command"], "exit": code, "output": output,
            "truncated": cut, "timed_out": timed_out, "seconds": round(time.monotonic() - started, 1)}
