"""Service access for SirisAI (ADR 110).

SirisAI is the only assistant, but the engineering library lives here, so
SirisAI needs to read it: `Authorization: Bearer <SIRISOS_SERVICE_KEY>`.
The key opens only the read and compute routes in SERVICE_ROUTES -- never
anything that uploads, edits or deletes. Everything else answers 403 to it.

Implemented as one ASGI middleware instead of a change to every route's
auth check: a request carrying the service key on an allowed route has its
Authorization swapped for a short-lived session token for the admin user,
so the routes' existing checks apply unchanged. The key must be at least
24 characters; a shorter one is ignored (and logged) rather than trusted.
"""

from __future__ import annotations

import hmac
import logging
import os
import re
from datetime import datetime, timedelta, timezone

import jwt

logger = logging.getLogger(__name__)

MIN_KEY_LENGTH = 24

SERVICE_ROUTES: list[tuple[str, re.Pattern[str]]] = [
    ("GET", re.compile(r"^/api/v1/hub/apps$")),
    ("GET", re.compile(r"^/api/v1/engineering/standards$")),
    ("GET", re.compile(r"^/api/v1/engineering/calculators$")),
    ("POST", re.compile(r"^/api/v1/engineering/calculators/[A-Za-z0-9_-]+/run$")),
    ("GET", re.compile(r"^/api/v1/projects$")),
    ("GET", re.compile(r"^/api/v1/engineering/sirishydro/evidence$")),
    # The Career record, for SirisAI's career_cpd_status and career_chartership_status (ADR 111).
    ("GET", re.compile(r"^/api/v1/career$")),
    ("GET", re.compile(r"^/api/v1/career/overview$")),
]

_warned_short = False


def service_key() -> str | None:
    global _warned_short
    key = os.getenv("SIRISOS_SERVICE_KEY", "").strip()
    if not key:
        return None
    if len(key) < MIN_KEY_LENGTH:
        if not _warned_short:
            logger.warning("SIRISOS_SERVICE_KEY is shorter than %d characters and is ignored.", MIN_KEY_LENGTH)
            _warned_short = True
        return None
    return key


def allowed(method: str, path: str) -> bool:
    return any(method == m and pattern.match(path) for m, pattern in SERVICE_ROUTES)


def _session_token() -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": os.getenv("SIRISOS_ADMIN_USERNAME", "brad"), "iat": now, "exp": now + timedelta(minutes=5),
               "iss": "sirisos-api", "via": "service-key"}
    return jwt.encode(payload, os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret"), algorithm="HS256")


class ServiceKeyMiddleware:
    def __init__(self, app) -> None:  # noqa: ANN001 - any ASGI app
        self.app = app

    async def __call__(self, scope, receive, send) -> None:  # noqa: ANN001
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        key = service_key()
        if key is None:
            return await self.app(scope, receive, send)
        headers = list(scope.get("headers") or [])
        auth = next((v.decode("latin-1") for k, v in headers if k == b"authorization"), "")
        presented = auth[7:].strip() if auth.startswith("Bearer ") else ""
        if not presented or not hmac.compare_digest(presented.encode(), key.encode()):
            return await self.app(scope, receive, send)
        if not allowed(scope["method"], scope["path"]):
            body = b'{"detail":"The service key only opens SirisOS\'s read and compute routes."}'
            await send({"type": "http.response.start", "status": 403,
                        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
            await send({"type": "http.response.body", "body": body})
            return
        swapped = [(k, v) for k, v in headers if k != b"authorization"]
        swapped.append((b"authorization", f"Bearer {_session_token()}".encode()))
        return await self.app({**scope, "headers": swapped}, receive, send)
