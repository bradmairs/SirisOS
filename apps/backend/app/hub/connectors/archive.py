"""Siris Engineering Archive (Fastify). Read-only external API with a
'read'-scope X-API-Key."""

from __future__ import annotations

import httpx

from app.hub.connectors.base import Connector, Metric, Widget, WidgetItem


class ArchiveConnector(Connector):
    id = "archive"
    name = "Engineering Archive"
    category = "engineering"
    icon = "archive"
    description = "Site photos, videos, drawings and assets."
    env_prefix = "ARCHIVE"

    def credentials_present(self) -> bool:
        return bool(self.setting("API_KEY"))

    def missing_config(self) -> str:
        return "Set ARCHIVE_URL and ARCHIVE_API_KEY (read scope) in .env."

    def headers(self) -> dict[str, str]:
        return {"X-API-Key": self.setting("API_KEY")}

    async def check(self, client: httpx.AsyncClient) -> str | None:
        await self.get_json(client, "/api/external/status")
        return None

    async def widget(self, client: httpx.AsyncClient) -> Widget:
        s = await self.get_json(client, "/api/external/status")
        review = int(s.get("needsReview") or 0)
        items = []
        scan = s.get("lastScan")
        if scan:
            items.append(
                WidgetItem(
                    title=f"Last scan: {scan.get('target')}",
                    subtitle=f"{scan.get('status')} · {str(scan.get('finishedAt') or scan.get('startedAt') or '')[:16].replace('T', ' ')}",
                    tone="warning" if scan.get("status") not in ("completed", "done", "ok", "success") else "neutral",
                )
            )
        return Widget(
            title="Archive",
            metrics=[
                Metric("Needs review", str(review), tone="warning" if review else "good"),
                Metric("Unassigned", str(s.get("unassignedMedia", 0))),
                Metric("Media", f"{int(s.get('totalMedia') or 0):,}"),
                Metric("Assets", str(s.get("totalAssets", 0))),
            ],
            items=items,
        )
