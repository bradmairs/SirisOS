"""Small helpers for reading from SirisAI's own routes (its hub contract and
brain routes) from SirisOS features. `get` never raises: None means SirisAI
isn't connected, is too old for the route, failed or timed out. `post` raises
SirisAIError with SirisAI's own message, for actions the person asked for."""

from __future__ import annotations

from typing import Any

import httpx

from app.hub.connectors.sirisai import SirisAIConnector
from app.hub.service import Hub, shared_client


class SirisAIError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def connector(hub: Hub) -> SirisAIConnector | None:
    found = hub.get("sirisai")
    return found if isinstance(found, SirisAIConnector) and found.configured else None


async def get(hub: Hub, path: str, params: Any = None, timeout: float = 20.0) -> Any:
    c = connector(hub)
    if c is None:
        return None
    try:
        response = await shared_client().get(f"{c.base_url}{path}", headers=c.headers(), params=params, timeout=timeout)
        if response.status_code >= 400:
            return None
        return response.json()
    except (httpx.HTTPError, ValueError):
        return None


async def post(hub: Hub, path: str, json: Any = None, timeout: float = 60.0, headers: dict[str, str] | None = None) -> Any:
    c = connector(hub)
    if c is None:
        raise SirisAIError("SirisAI isn't connected.", 503)
    try:
        response = await shared_client().post(f"{c.base_url}{path}", headers={**c.headers(), **(headers or {})}, json=json, timeout=timeout)
    except httpx.HTTPError as exc:
        raise SirisAIError(f"SirisAI unreachable: {type(exc).__name__}") from exc
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise SirisAIError(f"SirisAI: {detail}", 502 if response.status_code in (401, 403) else response.status_code)
    return response.json() if response.content else None


async def raw(hub: Hub, method: str, path: str, timeout: float = 60.0, **kwargs: Any) -> httpx.Response:
    """Pass a request through as it is (an upload, a CSV or page to hand back).
    Raises SirisAIError when SirisAI isn't there; the caller reads the status."""
    c = connector(hub)
    if c is None:
        raise SirisAIError("SirisAI isn't connected.", 503)
    try:
        return await shared_client().request(method, f"{c.base_url}{path}", headers=c.headers(), timeout=timeout, **kwargs)
    except httpx.HTTPError as exc:
        raise SirisAIError(f"SirisAI unreachable: {type(exc).__name__}") from exc
