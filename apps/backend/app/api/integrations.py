from datetime import datetime
import os
from typing import Literal

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.main import CurrentUsername

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


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


async def _probe(
    *,
    key: str,
    name: str,
    base_url: str | None,
    path: str,
    headers: dict[str, str] | None = None,
    version_header: str | None = None,
) -> IntegrationStatus:
    if not base_url:
        return IntegrationStatus(
            key=key,
            name=name,
            configured=False,
            available=False,
            status="unconfigured",
            detail="Not configured",
        )

    url = f"{base_url.rstrip('/')}{path}"
    started = datetime.now()
    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
        latency_ms = int((datetime.now() - started).total_seconds() * 1000)
        response.raise_for_status()
        version = response.headers.get(version_header) if version_header else None
        return IntegrationStatus(
            key=key,
            name=name,
            configured=True,
            available=True,
            status="healthy",
            detail="Connected",
            version=version,
            latency_ms=latency_ms,
        )
    except (httpx.HTTPError, ValueError) as exc:
        return IntegrationStatus(
            key=key,
            name=name,
            configured=True,
            available=False,
            status="warning",
            detail=f"Connection failed: {type(exc).__name__}",
        )


@router.get("/diagnostics", response_model=IntegrationDiagnosticsResponse)
async def integration_diagnostics(_: CurrentUsername) -> IntegrationDiagnosticsResponse:
    home_assistant_url = os.getenv("HOME_ASSISTANT_URL")
    home_assistant_token = os.getenv("HOME_ASSISTANT_TOKEN")
    plex_url = os.getenv("PLEX_URL")
    plex_token = os.getenv("PLEX_TOKEN")
    ollama_url = os.getenv("OLLAMA_URL")

    home_assistant_headers = (
        {"Authorization": f"Bearer {home_assistant_token}"}
        if home_assistant_token
        else None
    )
    plex_headers = {"X-Plex-Token": plex_token} if plex_token else None

    results = [
        await _probe(
            key="home_assistant",
            name="Home Assistant",
            base_url=home_assistant_url if home_assistant_token else None,
            path="/api/",
            headers=home_assistant_headers,
        ),
        await _probe(
            key="plex",
            name="Plex",
            base_url=plex_url if plex_token else None,
            path="/identity",
            headers=plex_headers,
            version_header="X-Plex-Version",
        ),
        await _probe(
            key="ollama",
            name="Ollama",
            base_url=ollama_url,
            path="/api/version",
        ),
    ]

    return IntegrationDiagnosticsResponse(
        integrations=results,
        healthy=sum(item.available for item in results),
        configured=sum(item.configured for item in results),
        total=len(results),
        generated_at=datetime.now().astimezone().isoformat(),
    )
