"""Shared bearer-JWT check for SirisOS API routes.

Tokens are issued by POST /api/v1/auth/login (app.main). Settings are read on
every call so tests and redeploys never see a stale secret.
"""

from __future__ import annotations

import os
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException

JWT_ALGORITHM = "HS256"


def require_user(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            authorization.removeprefix("Bearer ").strip(),
            os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret"),
            algorithms=[JWT_ALGORITHM],
            issuer="sirisos-api",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    username = payload.get("sub")
    if not isinstance(username, str) or username != os.getenv("SIRISOS_ADMIN_USERNAME", "brad"):
        raise HTTPException(status_code=401, detail="Invalid session user.")
    return username


CurrentUser = Annotated[str, Depends(require_user)]
