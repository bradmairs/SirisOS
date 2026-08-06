from datetime import datetime
import os
from typing import Annotated, Literal

import httpx
import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])
AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")


class IntegrationStatus(BaseModel):
    key: str
    name: str
    configured: bool
    available: bool
    status: Literal["healthy", "warning", "unconfigured"]
    detail: str
    version: str | None = None
    latency_ms: int | None = None


class IntegrationDiagnosticsResponse(BaseModel):
    integrations: list[IntegrationStatus]
    healthy: int
    configured: int
    total: int
    generated_at: str


def _authenticate(authorization: Annotated[str | None, Header()] = None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        payload = jwt.decode(
            authorization.removeprefix("Bearer ").strip(),
            JWT_SECRET,
            algorithms=["HS256"],
            issuer="sirisos-api",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session.") from exc
    if payload.get("sub") != AUTH_USERNAME:
        raise HTTPException(status_code=401, detail="Invalid session user.")


async def _probe(*, key: str, name: str, base_url: str | None, path: str, headers: dict[str, str] | None = None, version_header: str | None = None) -> IntegrationStatus:
    if not base_url:
        return IntegrationStatus(key=key, name=name, configured=False, available=False, status="unconfigured", detail="Not configured")
    started = datetime.now()
    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            response = await client.get(f"{base_url.rstrip('/')}{path}", headers=headers)
        latency_ms = int((datetime.now() - started).total_seconds() * 1000)
        response.raise_for_status()
        return IntegrationStatus(key=key, name=name, configured=True, available=True, status="healthy", detail="Connected", version=response.headers.get(version_header) if version_header else None, latency_ms=latency_ms)
    except (httpx.HTTPError, ValueError) as exc:
        return IntegrationStatus(key=key, name=name, configured=True, available=False, status="warning", detail=f"Connection failed: {type(exc).__name__}")


@router.get("/diagnostics", response_model=IntegrationDiagnosticsResponse)
async def integration_diagnostics(authorization: Annotated[str | None, Header()] = None) -> IntegrationDiagnosticsResponse:
    _authenticate(authorization)
    ha_url, ha_token = os.getenv("HOME_ASSISTANT_URL"), os.getenv("HOME_ASSISTANT_TOKEN")
    plex_url, plex_token = os.getenv("PLEX_URL"), os.getenv("PLEX_TOKEN")
    results = [
        await _probe(key="home_assistant", name="Home Assistant", base_url=ha_url if ha_token else None, path="/api/", headers={"Authorization": f"Bearer {ha_token}"} if ha_token else None),
        await _probe(key="plex", name="Plex", base_url=plex_url if plex_token else None, path="/identity", headers={"X-Plex-Token": plex_token} if plex_token else None, version_header="X-Plex-Version"),
        await _probe(key="ollama", name="Ollama", base_url=os.getenv("OLLAMA_URL"), path="/api/version"),
    ]
    return IntegrationDiagnosticsResponse(integrations=results, healthy=sum(item.available for item in results), configured=sum(item.configured for item in results), total=len(results), generated_at=datetime.now().astimezone().isoformat())
