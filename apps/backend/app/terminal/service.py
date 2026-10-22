"""The terminal (2.8): a shell on a machine at home, over SSH, from SirisOS.

Getting a shell takes three things:
1. a signed-in SirisOS session (the usual password or passkey);
2. a fresh code from an authenticator app, every time a terminal opens.
   2FA is set up once, and that needs the SirisOS password too, so a stolen
   session alone can't set it up or use it;
3. the unlock gives a ticket that works once, for one host, for 30 seconds,
   and the browser opens the terminal's WebSocket with it.

Hosts come only from SIRISOS_TERMINAL_HOSTS ("home=brad@192.168.0.100:22,
pi=pi@192.168.0.50"); nothing in the browser can name another address. SirisOS
signs in with its own SSH key (shown on the Terminal page for authorized_keys)
and pins each host's key the first time, refusing to connect if it changes.
"""

from __future__ import annotations

import os
import re
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

from app.terminal import store, totp

TICKET_SECONDS = 30
MAX_FAILURES = 5
FAILURE_WINDOW = 15 * 60
MAX_SESSIONS = 2
HOST_RE = re.compile(r"^(?P<name>[A-Za-z0-9_-]{1,32})=(?P<user>[A-Za-z0-9._-]{1,32})@(?P<host>[A-Za-z0-9.:-]{1,253}?)(?::(?P<port>\d{1,5}))?$")


@dataclass(frozen=True)
class Host:
    name: str
    user: str
    host: str
    port: int = 22

    @property
    def target(self) -> str:
        return f"{self.user}@{self.host}" + (f":{self.port}" if self.port != 22 else "")


def hosts() -> list[Host]:
    out: list[Host] = []
    for part in os.getenv("SIRISOS_TERMINAL_HOSTS", "").split(","):
        m = HOST_RE.match(part.strip())
        if m:
            out.append(Host(m["name"], m["user"], m["host"], int(m["port"] or 22)))
    return out


def find_host(name: str) -> Host | None:
    return next((h for h in hosts() if h.name == name), None)


def enabled() -> bool:
    return bool(hosts())


def _minutes(env: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(env, str(default))))
    except ValueError:
        return default


def idle_minutes() -> int:
    return _minutes("SIRISOS_TERMINAL_IDLE_MINUTES", 15)


def max_minutes() -> int:
    return _minutes("SIRISOS_TERMINAL_MAX_MINUTES", 120)


# -- SirisOS's SSH key ----------------------------------------------------------

def client_key():
    """SirisOS's ed25519 key, made on first use and kept in the data folder (mode 600)."""
    import asyncssh

    path = store.key_path()
    if path.exists():
        return asyncssh.read_private_key(str(path))
    key = asyncssh.generate_private_key("ssh-ed25519", comment="sirisos-terminal")
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    key.write_private_key(str(path))
    os.chmod(path, 0o600)
    return key


def public_key() -> str:
    return client_key().export_public_key().decode().strip()


def pinned_key(name: str) -> str | None:
    return (store.load().get("host_keys") or {}).get(name)


def pin(name: str, key_text: str) -> None:
    state = store.load()
    state.setdefault("host_keys", {})[name] = key_text
    store.save(state)


def forget(name: str) -> bool:
    state = store.load()
    found = (state.get("host_keys") or {}).pop(name, None) is not None
    store.save(state)
    return found


# -- 2FA ---------------------------------------------------------------------------

def two_factor() -> dict[str, Any]:
    t = store.load().get("totp") or {}
    return {"set_up": bool(t.get("confirmed")), "since": t.get("confirmed_at"),
            "broken": bool(t.get("confirmed")) and store.unseal(t.get("secret", "")) is None}


def begin_setup(account: str) -> dict[str, str]:
    """A new secret, waiting for its first code. Refused while 2FA is set up:
    turning it off (with a current code) comes first."""
    state = store.load()
    if (state.get("totp") or {}).get("confirmed") and not two_factor()["broken"]:
        raise PermissionError("2FA is already set up. Turn it off with a current code first.")
    secret = totp.new_secret()
    state["totp"] = {"secret": store.seal(secret), "confirmed": False, "created_at": store.now(), "last_step": 0}
    store.save(state)
    return {"secret": secret, "uri": totp.uri(secret, account)}


def _check(code: str, *, confirmed: bool) -> bool:
    state = store.load()
    t = state.get("totp") or {}
    if bool(t.get("confirmed")) != confirmed:
        return False
    secret = store.unseal(t.get("secret", ""))
    if secret is None:
        return False
    with _lock:
        step = totp.verify(secret, code, int(t.get("last_step", 0)))
        if step is None:
            return False
        t["last_step"] = step
        state["totp"] = t
        store.save(state)
    return True


def confirm_setup(code: str) -> bool:
    if not _check(code, confirmed=False):
        return False
    state = store.load()
    state["totp"].update(confirmed=True, confirmed_at=store.now())
    store.save(state)
    return True


def verify_code(code: str) -> bool:
    return _check(code, confirmed=True)


def turn_off() -> None:
    state = store.load()
    state.pop("totp", None)
    store.save(state)


# -- wrong-code lockout (its own, apart from the sign-in one) ------------------------

_failures: dict[str, deque[float]] = {}
_lock = threading.Lock()


def blocked_for(client: str) -> int:
    now = time.monotonic()
    with _lock:
        recent = _failures.get(client)
        # Wrong codes from anywhere count too: 2FA is one secret, not one per device.
        everyone = [t for q in _failures.values() for t in q if t > now - FAILURE_WINDOW]
        if recent:
            while recent and recent[0] < now - FAILURE_WINDOW:
                recent.popleft()
        mine = len(recent or ())
        if mine >= MAX_FAILURES:
            return int(recent[0] + FAILURE_WINDOW - now) + 1
        if len(everyone) >= MAX_FAILURES * 2:
            return int(min(everyone) + FAILURE_WINDOW - now) + 1
        return 0


def failed(client: str) -> None:
    with _lock:
        _failures.setdefault(client, deque()).append(time.monotonic())


def succeeded(client: str) -> None:
    with _lock:
        _failures.pop(client, None)


# -- tickets and live sessions -------------------------------------------------------

_tickets: dict[str, tuple[str, str, float]] = {}  # ticket -> (host, client, expires)
_sessions: dict[str, dict[str, Any]] = {}


def new_ticket(host: str, client: str) -> str:
    ticket = secrets.token_urlsafe(32)
    now = time.monotonic()
    with _lock:
        for k in [k for k, v in _tickets.items() if v[2] < now]:
            _tickets.pop(k, None)
        _tickets[ticket] = (host, client, now + TICKET_SECONDS)
    return ticket


def take_ticket(ticket: str) -> tuple[str, str] | None:
    """(host, client) for a live ticket; each works once."""
    with _lock:
        found = _tickets.pop(ticket, None)
    if not found or found[2] < time.monotonic():
        return None
    return found[0], found[1]


def open_session(host: str, client: str) -> str | None:
    with _lock:
        if len(_sessions) >= MAX_SESSIONS:
            return None
        sid = secrets.token_hex(8)
        _sessions[sid] = {"id": sid, "host": host, "client": client, "started": store.now()}
        return sid


def close_session(sid: str) -> None:
    with _lock:
        _sessions.pop(sid, None)


def sessions() -> list[dict[str, Any]]:
    with _lock:
        return list(_sessions.values())


def reset() -> None:
    with _lock:
        _failures.clear()
        _tickets.clear()
        _sessions.clear()
