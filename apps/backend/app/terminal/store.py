"""What the terminal keeps in the data folder:

- terminal.json: the authenticator secret (encrypted with a key derived from
  SIRISOS_JWT_SECRET, so a copy of the data folder alone can't make codes),
  the last code step used (codes work once), and each host's SSH key
  fingerprint, pinned the first time SirisOS connects.
- terminal/id_ed25519: SirisOS's own SSH key. Only its public half ever leaves.
- terminal-audit.jsonl: one line per unlock, refusal and session (never keystrokes).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.services import json_store


def _path() -> Path:
    return json_store.data_path("SIRISOS_TERMINAL_STATE_PATH", "terminal.json")


def key_path() -> Path:
    return _path().with_name("terminal") / "id_ed25519"


def audit_path() -> Path:
    return _path().with_name("terminal-audit.jsonl")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load() -> dict[str, Any]:
    return json_store.read(_path(), {})


def save(state: dict[str, Any]) -> None:
    json_store.write(_path(), state)
    os.chmod(_path(), 0o600)


def _fernet() -> Fernet:
    secret = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret").encode()
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"sirisos-terminal", info=b"totp-secret").derive(secret)
    return Fernet(base64.urlsafe_b64encode(key))


def seal(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def unseal(token: str) -> str | None:
    """None when SIRISOS_JWT_SECRET changed since 2FA was set up (set it up again)."""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None


def fingerprint(public_key_text: str) -> str:
    """SHA256:… the way ssh-keygen -lf shows it."""
    blob = base64.b64decode(public_key_text.split()[1])
    return "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")


def audit(event: str, **fields: Any) -> None:
    path = audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": now(), "event": event, **fields}, ensure_ascii=False) + "\n")


def recent_audit(limit: int = 20) -> list[dict[str, Any]]:
    try:
        lines = audit_path().read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    out = []
    for raw in reversed(lines[-limit * 3:]):
        try:
            out.append(json.loads(raw))
        except ValueError:
            continue
        if len(out) >= limit:
            break
    return out
