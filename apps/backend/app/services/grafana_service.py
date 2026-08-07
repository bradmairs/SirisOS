from dataclasses import dataclass
import base64
import os
import re

import httpx


_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class GrafanaDashboard:
    uid: str
    title: str
    url: str
    folder_title: str | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class GrafanaSnapshot:
    configured: bool
    available: bool
    dashboards: list[GrafanaDashboard]
    version: str | None = None
    error: str | None = None


class GrafanaService:
    """Server-side Grafana client. Grafana credentials never reach Flutter."""

    def __init__(self) -> None:
        self._base_url = os.getenv("GRAFANA_URL", "").rstrip("/")
        self._token = os.getenv("GRAFANA_TOKEN", "")
        self._rendering_enabled = os.getenv("GRAFANA_RENDERING_ENABLED", "false").lower() in {
            "1",
            "true",
            "yes",
        }

    @property
    def configured(self) -> bool:
        return bool(self._base_url and self._token)

    @property
    def rendering_enabled(self) -> bool:
        return self._rendering_enabled

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }

    async def snapshot(self) -> GrafanaSnapshot:
        if not self.configured:
            return GrafanaSnapshot(False, False, [], error="Grafana is not configured.")

        try:
            async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
                health_response = await client.get(
                    f"{self._base_url}/api/health",
                    headers=self._headers,
                )
                health_response.raise_for_status()
                health = health_response.json()
                version = str(health.get("version")) if isinstance(health, dict) and health.get("version") else None

                dashboards = await self._discover_dashboards(client)
            return GrafanaSnapshot(True, True, dashboards, version=version)
        except (httpx.HTTPError, ValueError) as exc:
            return GrafanaSnapshot(
                True,
                False,
                [],
                error=f"Grafana request failed: {type(exc).__name__}",
            )

    async def _discover_dashboards(self, client: httpx.AsyncClient) -> list[GrafanaDashboard]:
        # Grafana 12+ dashboard API. Fall back to the legacy search API for
        # older self-hosted installations; Grafana currently keeps it operative.
        try:
            response = await client.get(
                f"{self._base_url}/apis/dashboard.grafana.app/v1/namespaces/default/dashboards",
                params={"limit": 200},
                headers=self._headers,
            )
            if response.status_code == 200:
                payload = response.json()
                items = payload.get("items") if isinstance(payload, dict) else None
                if isinstance(items, list):
                    dashboards = []
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        spec = item.get("spec") if isinstance(item.get("spec"), dict) else {}
                        uid = str(spec.get("uid") or item.get("metadata", {}).get("name") or "")
                        title = str(spec.get("title") or uid)
                        if uid:
                            dashboards.append(
                                GrafanaDashboard(
                                    uid=uid,
                                    title=title,
                                    url=f"{self._base_url}/d/{uid}",
                                    tags=tuple(str(tag) for tag in spec.get("tags", []) if tag),
                                )
                            )
                    dashboards.sort(key=lambda item: item.title.lower())
                    return dashboards
        except (httpx.HTTPError, ValueError):
            pass

        response = await client.get(
            f"{self._base_url}/api/search/",
            params={"type": "dash-db", "limit": 200},
            headers=self._headers,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Grafana returned an invalid dashboard search payload.")

        dashboards = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            uid = str(item.get("uid") or "")
            title = str(item.get("title") or uid)
            relative_url = str(item.get("url") or "")
            if not uid:
                continue
            url = f"{self._base_url}{relative_url}" if relative_url.startswith("/") else f"{self._base_url}/d/{uid}"
            dashboards.append(
                GrafanaDashboard(
                    uid=uid,
                    title=title,
                    url=url,
                    folder_title=str(item.get("folderTitle")) if item.get("folderTitle") else None,
                    tags=tuple(str(tag) for tag in item.get("tags", []) if tag),
                )
            )
        dashboards.sort(key=lambda item: item.title.lower())
        return dashboards

    async def render_panel(
        self,
        *,
        dashboard_uid: str,
        slug: str,
        panel_id: str,
        width: int = 1000,
        height: int = 500,
    ) -> str:
        if not self.configured:
            raise RuntimeError("Grafana is not configured.")
        if not self.rendering_enabled:
            raise RuntimeError("Grafana image rendering is not enabled in SirisOS.")
        for value in (dashboard_uid, slug, panel_id):
            if not _SAFE_SEGMENT.fullmatch(value):
                raise ValueError("Invalid Grafana render identifier.")
        width = max(320, min(width, 2000))
        height = max(180, min(height, 1200))

        async with httpx.AsyncClient(timeout=35.0, follow_redirects=True) as client:
            response = await client.get(
                f"{self._base_url}/render/d-solo/{dashboard_uid}/{slug}",
                params={
                    "panelId": panel_id,
                    "width": width,
                    "height": height,
                    "tz": "UTC",
                },
                headers=self._headers,
            )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "image/png" not in content_type:
            raise RuntimeError("Grafana did not return a PNG render.")
        return base64.b64encode(response.content).decode("ascii")
