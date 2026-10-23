"""The terminal (2.8): authenticator codes, 2FA setup, unlock tickets, the
wrong-code lockout, and a real SSH session through the WebSocket."""

from __future__ import annotations

import asyncio
import json
import socket
import threading
from datetime import datetime, timedelta, timezone

import asyncssh
import jwt
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.entrypoint import app
from app.security import service as security
from app.terminal import service, store, totp

RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # base32 of "12345678901234567890"
ORIGIN = "http://testserver"


def _auth() -> dict[str, str]:
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": "brad", "iat": now, "exp": now + timedelta(hours=1), "iss": "sirisos-api"},
                       "change-this-development-secret", algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def test_codes_match_rfc_6238():
    assert totp.code_at(RFC_SECRET, 59 // 30) == "287082"
    assert totp.code_at(RFC_SECRET, 1111111109 // 30) == "081804"
    assert totp.code_at(RFC_SECRET, 1234567890 // 30) == "005924"


def test_a_code_works_once_and_allows_one_step_of_drift():
    t = 1234567890.0
    step = totp.verify(RFC_SECRET, "005 924", 0, now=t)
    assert step == 1234567890 // 30
    assert totp.verify(RFC_SECRET, "005924", step, now=t) is None  # used
    assert totp.verify(RFC_SECRET, totp.code_at(RFC_SECRET, step + 1), step, now=t) == step + 1  # phone a bit fast
    assert totp.verify(RFC_SECRET, totp.code_at(RFC_SECRET, step + 3), 0, now=t) is None
    assert totp.verify(RFC_SECRET, "12345", 0, now=t) is None
    assert "secret=" + RFC_SECRET in totp.uri(RFC_SECRET, "brad") and totp.uri(RFC_SECRET, "brad").startswith("otpauth://totp/SirisOS%3Abrad?")


@pytest.fixture
def clock(monkeypatch):
    """Code steps under the test's control, so 'the next code' is predictable."""
    state = {"step": 60_000_000}
    monkeypatch.setattr(totp, "current_step", lambda now=None: state["step"])
    return state


@pytest.fixture
def client(tmp_path, monkeypatch, clock):
    monkeypatch.setenv("SIRISOS_TERMINAL_STATE_PATH", str(tmp_path / "terminal.json"))
    monkeypatch.setenv("SIRISOS_TERMINAL_HOSTS", "home=brad@127.0.0.1:2222, bad entry, pi=pi@10.0.0.5")
    service.reset()
    security.reset()
    yield TestClient(app, headers={"Origin": ORIGIN})
    service.reset()
    security.reset()


def _code(secret: str, clock, ahead: int = 0) -> str:
    return totp.code_at(secret, clock["step"] + ahead)


def _set_up(client, clock) -> str:
    started = client.post("/api/v1/terminal/2fa/setup", headers=_auth(), json={"password": "change-me"}).json()
    assert client.post("/api/v1/terminal/2fa/confirm", headers=_auth(), json={"code": _code(started["secret"], clock)}).status_code == 200
    return started["secret"]


def test_off_until_hosts_are_set(client, monkeypatch):
    monkeypatch.setenv("SIRISOS_TERMINAL_HOSTS", "")
    assert client.get("/api/v1/terminal").status_code == 401
    s = client.get("/api/v1/terminal", headers=_auth()).json()
    assert s["enabled"] is False and s["public_key"] is None and s["hosts"] == []
    assert client.post("/api/v1/terminal/2fa/setup", headers=_auth(), json={"password": "change-me"}).status_code == 404
    assert client.post("/api/v1/terminal/unlock", headers=_auth(), json={"host": "home", "code": "123456"}).status_code == 404


def test_setting_up_2fa_needs_the_password_and_a_first_code(client, clock, tmp_path):
    s = client.get("/api/v1/terminal", headers=_auth()).json()
    assert [h["name"] for h in s["hosts"]] == ["home", "pi"] and s["hosts"][0]["target"] == "brad@127.0.0.1:2222"
    assert s["public_key"].startswith("ssh-ed25519 ") and s["two_factor"]["set_up"] is False
    assert oct((tmp_path / "terminal" / "id_ed25519").stat().st_mode & 0o777) == "0o600"

    assert client.post("/api/v1/terminal/2fa/setup", headers=_auth(), json={"password": "nope"}).status_code == 401
    started = client.post("/api/v1/terminal/2fa/setup", headers=_auth(), json={"password": "change-me"}).json()
    assert started["uri"].startswith("otpauth://totp/") and "<svg" in started["qr_svg"]
    assert started["secret"] not in (tmp_path / "terminal.json").read_text()  # stored encrypted

    assert client.post("/api/v1/terminal/2fa/confirm", headers=_auth(), json={"code": "000000"}).status_code == 401
    assert client.post("/api/v1/terminal/2fa/confirm", headers=_auth(), json={"code": _code(started["secret"], clock)}).status_code == 200
    assert client.get("/api/v1/terminal", headers=_auth()).json()["two_factor"]["set_up"] is True
    # A second setup can't quietly replace it.
    assert client.post("/api/v1/terminal/2fa/setup", headers=_auth(), json={"password": "change-me"}).status_code == 409


def test_unlock_needs_a_fresh_code_every_time(client, clock):
    assert client.post("/api/v1/terminal/unlock", headers=_auth(), json={"host": "home", "code": "123456"}).status_code == 403
    secret = _set_up(client, clock)
    # The code that confirmed setup can't be used again.
    assert client.post("/api/v1/terminal/unlock", headers=_auth(), json={"host": "home", "code": _code(secret, clock)}).status_code == 401
    clock["step"] += 1
    r = client.post("/api/v1/terminal/unlock", headers=_auth(), json={"host": "home", "code": _code(secret, clock)})
    assert r.status_code == 200 and r.json()["expires_in"] == 30
    assert client.post("/api/v1/terminal/unlock", headers=_auth(), json={"host": "home", "code": _code(secret, clock)}).status_code == 401
    assert client.post("/api/v1/terminal/unlock", headers=_auth(), json={"host": "elsewhere", "code": _code(secret, clock, 1)}).status_code == 404
    events = [e["event"] for e in client.get("/api/v1/terminal", headers=_auth()).json()["activity"]]
    assert "unlocked" in events and "code-refused" in events and "2fa-on" in events


def test_wrong_codes_lock_the_terminal(client, clock):
    secret = _set_up(client, clock)
    for _ in range(service.MAX_FAILURES):
        assert client.post("/api/v1/terminal/unlock", headers=_auth(), json={"host": "home", "code": "000000"}).status_code == 401
    clock["step"] += 1
    r = client.post("/api/v1/terminal/unlock", headers=_auth(), json={"host": "home", "code": _code(secret, clock)})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0


def test_turning_2fa_off_needs_password_and_code(client, clock):
    secret = _set_up(client, clock)
    clock["step"] += 1
    assert client.post("/api/v1/terminal/2fa/off", headers=_auth(), json={"password": "change-me", "code": "000000"}).status_code == 401
    assert client.post("/api/v1/terminal/2fa/off", headers=_auth(), json={"password": "nope", "code": _code(secret, clock)}).status_code == 401
    assert client.post("/api/v1/terminal/2fa/off", headers=_auth(), json={"password": "change-me", "code": _code(secret, clock)}).status_code == 200
    assert client.get("/api/v1/terminal", headers=_auth()).json()["two_factor"]["set_up"] is False


def test_a_changed_jwt_secret_means_setting_2fa_up_again(client, clock, monkeypatch):
    _set_up(client, clock)
    monkeypatch.setenv("SIRISOS_JWT_SECRET", "x" * 40)
    assert service.two_factor() == {"set_up": True, "since": service.two_factor()["since"], "broken": True}
    assert service.verify_code(_code(RFC_SECRET, clock)) is False


def test_websocket_needs_same_origin_and_a_live_ticket(client, clock):
    with pytest.raises(WebSocketDisconnect) as exc:
        with TestClient(app).websocket_connect("/api/v1/terminal/ws?ticket=x"):
            pass
    assert exc.value.code == 4403
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/v1/terminal/ws?ticket=made-up", headers={"Origin": ORIGIN}):
            pass
    assert exc.value.code == 4401
    ticket = service.new_ticket("home", "1.2.3.4")
    service.take_ticket(ticket)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/api/v1/terminal/ws?ticket={ticket}", headers={"Origin": ORIGIN}):
            pass
    assert exc.value.code == 4401


# -- a real SSH server ---------------------------------------------------------------

class _Shell:
    """An SSH server on 127.0.0.1 that greets, then echoes each line it's sent."""

    def __init__(self, authorized: str):
        self.host_key = asyncssh.generate_private_key("ssh-ed25519")
        self.authorized = asyncssh.import_authorized_keys(authorized)
        self.loop = asyncio.new_event_loop()
        self.started = threading.Event()
        self.sizes: list[tuple[int, int]] = []
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        threading.Thread(target=self._run, daemon=True).start()
        assert self.started.wait(10)

    async def _session(self, process):
        if process.command:  # a one-off command (a shortcut), not a shell
            if process.command == "sleep 99":
                await asyncio.sleep(5)
            process.stdout.write(f"ran: {process.command}\n")
            if "fail" in process.command:
                process.stderr.write("it failed\n")
                process.exit(3)
            else:
                process.exit(0)
            return
        process.stdout.write(f"hello {process.get_extra_info('username')}\r\n")
        while True:
            try:
                line = await process.stdin.readline()
            except asyncssh.TerminalSizeChanged:
                continue  # the browser resized the terminal
            except asyncssh.BreakReceived:
                break
            if not line:
                break
            if line.strip() == "size":
                cols, rows = process.get_terminal_size()[:2]
                process.stdout.write(f"size {cols}x{rows}\r\n")
            else:
                process.stdout.write(f"you said {line.strip()}\r\n")
        process.exit(0)

    def _run(self):
        asyncio.set_event_loop(self.loop)

        async def start():
            self.server = await asyncssh.create_server(
                asyncssh.SSHServer, "127.0.0.1", self.port, server_host_keys=[self.host_key],
                authorized_client_keys=self.authorized, process_factory=self._session)
            self.started.set()

        self.loop.run_until_complete(start())
        self.loop.run_forever()

    def stop(self):
        self.loop.call_soon_threadsafe(self.server.close)
        self.loop.call_soon_threadsafe(self.loop.stop)


def _read_until(ws, text: str) -> str:
    seen = ""
    for _ in range(50):
        msg = ws.receive()
        if msg.get("bytes"):
            seen += msg["bytes"].decode()
        elif msg.get("text"):
            seen += msg["text"]
        if text in seen:
            return seen
    raise AssertionError(f"never saw {text!r} in {seen!r}")


def test_a_session_runs_a_shell_and_pins_the_host_key(client, clock, monkeypatch):
    shell = _Shell(service.public_key())
    monkeypatch.setenv("SIRISOS_TERMINAL_HOSTS", f"home=brad@127.0.0.1:{shell.port}")
    try:
        secret = _set_up(client, clock)
        clock["step"] += 1
        ticket = client.post("/api/v1/terminal/unlock", headers=_auth(), json={"host": "home", "code": _code(secret, clock)}).json()["ticket"]
        with client.websocket_connect(f"/api/v1/terminal/ws?ticket={ticket}", headers={"Origin": ORIGIN}) as ws:
            ready = json.loads(ws.receive_text())
            assert ready["type"] == "ready" and ready["target"] == f"brad@127.0.0.1:{shell.port}" and ready["idle_minutes"] == 15
            assert "hello brad" in _read_until(ws, "hello brad")
            ws.send_text(json.dumps({"type": "resize", "cols": 120, "rows": 40}))
            ws.send_text(json.dumps({"type": "input", "data": "size\r"}))
            assert "size 120x40" in _read_until(ws, "size 120x40")
            ws.send_text(json.dumps({"type": "input", "data": "ls\r"}))
            assert "you said ls" in _read_until(ws, "you said ls")
            assert len(client.get("/api/v1/terminal", headers=_auth()).json()["sessions"]) == 1
        pinned = service.pinned_key("home")
        assert pinned and store.fingerprint(pinned) == store.fingerprint(shell.host_key.export_public_key().decode())
        status = client.get("/api/v1/terminal", headers=_auth()).json()
        assert status["hosts"][0]["host_key"].startswith("SHA256:")
        events = [e["event"] for e in status["activity"]]
        assert {"session-start", "session-end", "host-key-pinned"} <= set(events)

        # The ticket was single use.
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f"/api/v1/terminal/ws?ticket={ticket}", headers={"Origin": ORIGIN}):
                pass
    finally:
        shell.stop()


def test_a_changed_host_key_is_refused(client, clock, monkeypatch):
    shell = _Shell(service.public_key())
    monkeypatch.setenv("SIRISOS_TERMINAL_HOSTS", f"home=brad@127.0.0.1:{shell.port}")
    service.pin("home", asyncssh.generate_private_key("ssh-ed25519").export_public_key().decode().strip())
    try:
        secret = _set_up(client, clock)
        clock["step"] += 1
        ticket = client.post("/api/v1/terminal/unlock", headers=_auth(), json={"host": "home", "code": _code(secret, clock)}).json()["ticket"]
        with client.websocket_connect(f"/api/v1/terminal/ws?ticket={ticket}", headers={"Origin": ORIGIN}) as ws:
            msg = json.loads(ws.receive_text())
        assert msg["type"] == "error" and "SSH key has changed" in msg["message"] and "terminal-forget-host" in msg["message"]
        assert service.forget("home") is True
    finally:
        shell.stop()


def test_idle_sessions_close(client, clock, monkeypatch):
    shell = _Shell(service.public_key())
    monkeypatch.setenv("SIRISOS_TERMINAL_HOSTS", f"home=brad@127.0.0.1:{shell.port}")
    monkeypatch.setattr(service, "idle_minutes", lambda: 0.01)
    monkeypatch.setattr("app.terminal.api.asyncio.sleep", _fast_sleep)
    try:
        secret = _set_up(client, clock)
        clock["step"] += 1
        ticket = client.post("/api/v1/terminal/unlock", headers=_auth(), json={"host": "home", "code": _code(secret, clock)}).json()["ticket"]
        with client.websocket_connect(f"/api/v1/terminal/ws?ticket={ticket}", headers={"Origin": ORIGIN}) as ws:
            seen = _read_until(ws, '"ended"')
        assert "no typing for a while" in seen
        ends = [e for e in store.recent_audit() if e["event"] == "session-end"]
        assert ends[0]["reason"] == "idle"
    finally:
        shell.stop()


_real_sleep = asyncio.sleep


async def _fast_sleep(seconds):
    await _real_sleep(min(seconds, 0.2))



def _unlock(client, clock, secret) -> str:
    clock["step"] += 1
    return client.post("/api/v1/terminal/unlock", headers=_auth(), json={"host": "home", "code": _code(secret, clock)}).json()["ticket"]


def test_shortcuts_run_behind_a_fresh_code(client, clock, monkeypatch):
    shell = _Shell(service.public_key())
    monkeypatch.setenv("SIRISOS_TERMINAL_HOSTS", f"home=brad@127.0.0.1:{shell.port}")
    try:
        listed = client.get("/api/v1/terminal/commands", headers=_auth()).json()
        assert [c["name"] for c in listed["commands"]] == ["What's running", "Disk space", "Memory and load"] and listed["seconds"] == 60
        made = client.post("/api/v1/terminal/commands", headers=_auth(), json={"name": "Restart SirisAI", "command": "cd ~/sirisai && docker compose restart"}).json()
        assert made["builtin"] is False and made["host"] is None
        assert client.post("/api/v1/terminal/commands", headers=_auth(), json={"name": "x", "command": "y", "host": "nas"}).status_code == 404

        secret = _set_up(client, clock)
        r = client.post("/api/v1/terminal/run", headers=_auth(), json={"ticket": _unlock(client, clock, secret), "command": made["id"]}).json()
        assert r["exit"] == 0 and r["output"] == "ran: cd ~/sirisai && docker compose restart\n" and r["host"] == "home"

        ticket = _unlock(client, clock, secret)
        assert client.post("/api/v1/terminal/run", headers=_auth(), json={"ticket": ticket, "command": "builtin:disk"}).status_code == 200
        again = client.post("/api/v1/terminal/run", headers=_auth(), json={"ticket": ticket, "command": "builtin:disk"})
        assert again.status_code == 401  # each run needs its own unlock

        events = [e["event"] for e in store.recent_audit()]
        assert "shortcut-run" in events and "shortcut-done" in events and "shortcut-saved" in events
        assert client.delete(f"/api/v1/terminal/commands/{made['id']}", headers=_auth()).json() == {"removed": True}
        assert client.delete("/api/v1/terminal/commands/builtin:disk", headers=_auth()).status_code == 404
    finally:
        shell.stop()


def test_a_failing_or_slow_shortcut(client, clock, monkeypatch):
    shell = _Shell(service.public_key())
    monkeypatch.setenv("SIRISOS_TERMINAL_HOSTS", f"home=brad@127.0.0.1:{shell.port}")
    monkeypatch.setenv("SIRISOS_TERMINAL_COMMAND_SECONDS", "5")
    from app.terminal import commands

    monkeypatch.setattr(commands, "seconds", lambda: 1)
    try:
        bad = client.post("/api/v1/terminal/commands", headers=_auth(), json={"name": "Fails", "command": "fail please"}).json()
        slow = client.post("/api/v1/terminal/commands", headers=_auth(), json={"name": "Slow", "command": "sleep 99"}).json()
        secret = _set_up(client, clock)
        r = client.post("/api/v1/terminal/run", headers=_auth(), json={"ticket": _unlock(client, clock, secret), "command": bad["id"]}).json()
        assert r["exit"] == 3 and "it failed" in r["output"]
        r = client.post("/api/v1/terminal/run", headers=_auth(), json={"ticket": _unlock(client, clock, secret), "command": slow["id"]}).json()
        assert r["timed_out"] is True and r["exit"] is None
    finally:
        shell.stop()
