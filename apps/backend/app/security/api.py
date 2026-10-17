"""Passkey sign-in and the security page.

    POST   /api/v1/auth/passkeys/login/options     a challenge (no sign-in needed)
    POST   /api/v1/auth/passkeys/login             {id, response}: a session, like the password login
    POST   /api/v1/auth/passkeys/register/options  signed in: a challenge to add a passkey
    POST   /api/v1/auth/passkeys/register          signed in: {response, label}
    GET    /api/v1/auth/passkeys                   signed in: this install's passkeys
    DELETE /api/v1/auth/passkeys/{id}              signed in: remove one
    GET    /api/v1/security                        signed in: the settings check

The relying party is the host SirisOS is opened on (SIRISOS_PASSKEY_RP_ID to
pin it). Browsers don't allow passkeys on a bare IP address.
"""

from __future__ import annotations

import ipaddress
import os
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import require_user
from app.security import service, webauthn

router = APIRouter(tags=["authentication"])


def rp_id_for(request: Request) -> str:
    pinned = os.getenv("SIRISOS_PASSKEY_RP_ID", "").strip()
    if pinned:
        return pinned
    origin = request.headers.get("origin") or ""
    host = urlsplit(origin).hostname or request.url.hostname or ""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return host
    raise HTTPException(status_code=400, detail="Passkeys need SirisOS opened on a name (like sirisos.home), not an IP address.")


class Ceremony(BaseModel):
    challenge: str = Field(min_length=10, max_length=200)
    id: str = Field(default="", max_length=1500)
    response: dict[str, Any]
    label: str = Field(default="", max_length=60)


@router.post("/api/v1/auth/passkeys/register/options", dependencies=[Depends(require_user)])
def register_options(request: Request, user: str = Depends(require_user)) -> dict[str, Any]:
    rp_id = rp_id_for(request)
    return {
        "challenge": service.new_challenge("register", rp_id),
        "rp": {"id": rp_id, "name": "SirisOS"},
        "user": {"id": webauthn.b64url(user.encode()), "name": user, "displayName": user.capitalize()},
        "pubKeyCredParams": [{"type": "public-key", "alg": webauthn.ES256}, {"type": "public-key", "alg": webauthn.RS256}],
        "authenticatorSelection": {"residentKey": "required", "userVerification": "required"},
        "attestation": "none",
        "excludeCredentials": [{"type": "public-key", "id": p.id} for p in service.passkeys() if p.rp_id == rp_id],
        "timeout": service.CHALLENGE_SECONDS * 1000,
    }


@router.post("/api/v1/auth/passkeys/register", dependencies=[Depends(require_user)])
def register(body: Ceremony) -> dict[str, Any]:
    rp_id = service.take_challenge(body.challenge, "register")
    if rp_id is None:
        raise HTTPException(status_code=400, detail="That took too long or was already used: try again.")
    try:
        auth = webauthn.verify_registration(body.response, body.challenge, rp_id)
    except webauthn.WebAuthnError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    item = service.Passkey(id=webauthn.b64url(auth.credential_id), label=body.label.strip() or "Passkey",
                           public_key=webauthn.b64url(auth.public_key), alg=auth.alg, sign_count=auth.sign_count,
                           rp_id=rp_id, created_at=service._now())
    service.add_passkey(item)
    return service.public(item)


@router.post("/api/v1/auth/passkeys/login/options")
def login_options(request: Request) -> dict[str, Any]:
    rp_id = rp_id_for(request)
    return {"challenge": service.new_challenge("login", rp_id), "rpId": rp_id, "userVerification": "required",
            "allowCredentials": [], "timeout": service.CHALLENGE_SECONDS * 1000}


def client_of(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[-1].strip() or (request.client.host if request.client else "unknown")


@router.post("/api/v1/auth/passkeys/login")
def login(body: Ceremony, request: Request) -> dict[str, Any]:
    from app.main import _create_access_token, AUTH_USERNAME

    client = client_of(request)
    wait = service.blocked_for(client)
    if wait:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again soon.", headers={"Retry-After": str(wait)})
    rp_id = service.take_challenge(body.challenge, "login")
    items = service.passkeys()
    found = next((p for p in items if p.id == body.id), None)
    if rp_id is None or found is None or found.rp_id != rp_id:
        service.failed(client)
        raise HTTPException(status_code=401, detail="That passkey isn't set up for SirisOS here.")
    try:
        count = webauthn.verify_assertion(body.response, body.challenge, rp_id, webauthn.unb64url(found.public_key), found.alg, found.sign_count)
    except webauthn.WebAuthnError as exc:
        service.failed(client)
        raise HTTPException(status_code=401, detail=str(exc)) from None
    found.sign_count, found.last_used = count, service._now()
    service.save_passkeys(items)
    service.succeeded(client)
    token, expires_in = _create_access_token(AUTH_USERNAME)
    return {"access_token": token, "token_type": "bearer", "expires_in": expires_in, "username": AUTH_USERNAME}


@router.get("/api/v1/auth/passkeys", dependencies=[Depends(require_user)])
def list_passkeys() -> dict[str, Any]:
    return {"passkeys": [service.public(p) for p in service.passkeys()]}


@router.delete("/api/v1/auth/passkeys/{cred_id}", dependencies=[Depends(require_user)])
def delete_passkey(cred_id: str) -> dict[str, Any]:
    if not service.remove_passkey(cred_id):
        raise HTTPException(status_code=404, detail="No such passkey.")
    return {"removed": True}


@router.get("/api/v1/security", dependencies=[Depends(require_user)])
def security_check() -> dict[str, Any]:
    return {"checks": service.checks(), "passkeys": len(service.passkeys())}
