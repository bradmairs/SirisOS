"""The connector contract every Siris app tile implements (ADR 106).

A connector knows how to reach one app server-side: whether it is
configured, how healthy it is, and (optionally) a small normalised widget
for the home screen. Credentials never leave the server.
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Mapping

import httpx

State = Literal["ok", "degraded", "down", "unconfigured"]
Category = Literal["assistant", "work", "engineering", "life"]
Tone = Literal["neutral", "good", "warning", "critical"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AppStatus:
    state: State
    detail: str = ""
    latency_ms: int | None = None
    version: str | None = None
    checked_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Metric:
    label: str
    value: str
    tone: Tone = "neutral"


@dataclass
class WidgetItem:
    title: str
    subtitle: str = ""
    url: str | None = None
    tone: Tone = "neutral"


@dataclass
class Widget:
    title: str
    metrics: list[Metric] = field(default_factory=list)
    items: list[WidgetItem] = field(default_factory=list)
    empty: str = ""
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SearchHit:
    """One result from an app's own search, normalised for SirisOS search (ADR 109)."""

    title: str
    subtitle: str = ""
    url: str | None = None
    kind: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "subtitle": self.subtitle, "url": self.url, "kind": self.kind}


class ConnectorError(Exception):
    """A failure worth showing on the tile, e.g. "unauthorised"."""

    def __init__(self, message: str, state: State = "down") -> None:
        super().__init__(message)
        self.state = state


class Connector:
    id: str = ""
    name: str = ""
    category: Category = "work"
    icon: str = "app"
    description: str = ""
    # Env var prefix: <PREFIX>_URL, <PREFIX>_PUBLIC_URL, ...
    env_prefix: str = ""
    # Launch-only connectors have no server-side API to check.
    launch_only: bool = False
    default_launch_url: str | None = None

    def __init__(self, env: Mapping[str, str]) -> None:
        self.env = env

    # -- configuration -----------------------------------------------------

    def setting(self, suffix: str) -> str:
        return (self.env.get(f"{self.env_prefix}_{suffix}") or "").strip()

    @property
    def base_url(self) -> str:
        return self.setting("URL").rstrip("/")

    @property
    def public_url(self) -> str:
        """*_PUBLIC_URL as a full address. A bare domain ("pm.example.org")
        would otherwise be a relative link and open SirisOS itself, so it
        gets https://. App schemes such as jefit:// are left alone."""
        return with_scheme(self.setting("PUBLIC_URL"))

    @property
    def launch_url(self) -> str | None:
        return self.public_url or self.base_url or self.default_launch_url

    @property
    def configured(self) -> bool:
        return bool(self.launch_url) if self.launch_only else bool(self.base_url) and self.credentials_present()

    def credentials_present(self) -> bool:
        return True

    def missing_config(self) -> str:
        return f"Set {self.env_prefix}_URL in .env."

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "icon": self.icon,
            "description": self.description,
            "launch_url": self.launch_url,
            "launch_only": self.launch_only,
            "configured": self.configured,
        }

    # -- runtime -----------------------------------------------------------

    async def status(self, client: httpx.AsyncClient) -> AppStatus:
        if self.launch_only:
            return AppStatus(state="ok" if self.configured else "unconfigured", detail="Launch only")
        if not self.configured:
            return AppStatus(state="unconfigured", detail=self.missing_config())
        started = time.perf_counter()
        try:
            version = await self.check(client)
        except ConnectorError as exc:
            return AppStatus(state=exc.state, detail=str(exc), latency_ms=_ms(started))
        except httpx.TimeoutException:
            return AppStatus(state="down", detail="Timed out", latency_ms=_ms(started))
        except httpx.HTTPError as exc:
            return AppStatus(state="down", detail=f"Unreachable: {type(exc).__name__}", latency_ms=_ms(started))
        return AppStatus(state="ok", detail="", latency_ms=_ms(started), version=version)

    async def check(self, client: httpx.AsyncClient) -> str | None:
        """Raise ConnectorError/httpx errors when unhealthy; may return a version."""
        raise NotImplementedError

    async def widget(self, client: httpx.AsyncClient) -> Widget | None:
        return None

    async def search(self, client: httpx.AsyncClient, query: str) -> list[SearchHit]:
        """The app's own search, if it has one SirisOS can call (ADR 109)."""
        raise NotImplementedError

    # -- helpers -----------------------------------------------------------

    def headers(self) -> dict[str, str]:
        return {}

    async def get_json(self, client: httpx.AsyncClient, path: str, **kwargs: Any) -> Any:
        response = await client.get(f"{self.base_url}{path}", headers=self.headers(), **kwargs)
        raise_for_status(response)
        return response.json()


def raise_for_status(response: httpx.Response) -> None:
    if response.status_code in (401, 403):
        raise ConnectorError("Unauthorised: check the credentials in .env", state="degraded")
    if response.status_code >= 400:
        raise ConnectorError(f"HTTP {response.status_code}", state="degraded" if response.status_code < 500 else "down")


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def with_scheme(url: str) -> str:
    """'pm.example.org' -> 'https://pm.example.org'; full URLs and app schemes unchanged."""
    url = url.strip()
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        return url if url.endswith("://") else url.rstrip("/")
    url = url.strip("/")
    return f"https://{url}" if url else ""
