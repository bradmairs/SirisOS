"""The sign-in secret and password, safe now the code is public (9.5).

SIRISOS_JWT_SECRET signs every session. The code used to fall back to a fixed
development value when it wasn't set, and with the code public, anyone could sign
a session with it. Now a missing, known or short secret is never used: SirisOS
makes a random one, keeps it in the data folder (`jwt-secret`, readable by its
owner only) and uses that, so an install without the setting is still safe (and
the Security page still says to set it).

The admin password works the same way: a missing or known one ("change-me",
"change-this-password") never signs in. Passkeys still work, and
scripts/reset-password.sh sets a real one.

Tests (and local development) opt in to the old fixed values with
SIRISOS_ALLOW_DEV_SECRETS=1; nothing deployed sets it.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

DEV_SECRET = "change-this-development-secret"
DEV_PASSWORD = "change-me"
KNOWN_SECRETS = {DEV_SECRET, "replace-with-a-long-random-secret", "change-this-secret", ""}
KNOWN_PASSWORDS = {DEV_PASSWORD, "change-this-password", ""}
_cached: tuple[tuple[str, bool, str], str] | None = None  # (what the environment said, the secret in use)


def dev_allowed() -> bool:
    return os.getenv("SIRISOS_ALLOW_DEV_SECRETS", "") in ("1", "true", "yes")


def configured_secret_ok() -> bool:
    """SIRISOS_JWT_SECRET is set to something long and not a published default."""
    s = os.getenv("SIRISOS_JWT_SECRET", "")
    return s not in KNOWN_SECRETS and len(s) >= 32


def _stored() -> str:
    path = Path(os.getenv("SIRISOS_DATA_DIR", "/app/data")) / "jwt-secret"
    try:
        found = path.read_text(encoding="utf-8").strip()
        if len(found) >= 32:
            return found
    except OSError:
        pass
    made = secrets.token_hex(32)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(made, encoding="utf-8")
        os.chmod(path, 0o600)
    except OSError:
        pass  # can't keep it: sessions last until a restart, still unforgeable
    return made


def jwt_secret() -> str:
    """The secret that signs sessions: the configured one when it's strong, else SirisOS's own random one."""
    global _cached
    env = os.getenv("SIRISOS_JWT_SECRET", "")
    said = (env, dev_allowed(), os.getenv("SIRISOS_DATA_DIR", ""))
    if _cached and _cached[0] == said:
        return _cached[1]
    if configured_secret_ok() or (dev_allowed() and env):
        use = env
    elif dev_allowed():
        use = DEV_SECRET
    else:
        use = _stored()
    _cached = (said, use)
    return use


def admin_password() -> str | None:
    """The password that may sign in, or None when it's missing or a published default."""
    p = os.getenv("SIRISOS_ADMIN_PASSWORD", "")
    if dev_allowed():
        return p or DEV_PASSWORD
    return None if p in KNOWN_PASSWORDS else p
