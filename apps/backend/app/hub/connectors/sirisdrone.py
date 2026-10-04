"""SirisDrone Studio (FastAPI). Drone photo/video editor that exports to the
NAS. No API key: the UI is open unless its optional Basic auth is on."""

from __future__ import annotations

import httpx

from app.hub.connectors.base import Connector, Metric, Widget, WidgetItem


class SirisDroneConnector(Connector):
    id = "sirisdrone"
    name = "SirisDrone"
    category = "life"
    icon = "drone"
    description = "Crop, grade and stamp drone shots, then export to the NAS."
    env_prefix = "SIRISDRONE"

    def auth(self) -> httpx.BasicAuth | None:
        user, password = self.setting("USERNAME"), self.setting("PASSWORD")
        return httpx.BasicAuth(user, password) if user and password else None

    async def get_json(self, client: httpx.AsyncClient, path: str, **kwargs):
        if (auth := self.auth()) is not None:
            kwargs.setdefault("auth", auth)
        return await super().get_json(client, path, **kwargs)

    async def check(self, client: httpx.AsyncClient) -> str | None:
        await self.get_json(client, "/api/config")
        return None

    async def widget(self, client: httpx.AsyncClient) -> Widget:
        config = await self.get_json(client, "/api/config")
        media = await self.get_json(client, "/api/media")
        jobs = await self.get_json(client, "/api/jobs")
        photos = sum(1 for m in media if m.get("kind") == "photo")
        videos = sum(1 for m in media if m.get("kind") == "video")
        active = [j for j in jobs if j.get("status") in ("queued", "running")]
        failed = [j for j in jobs if j.get("status") == "error"]
        nas_ok = all(r.get("available") for r in config.get("output_roots") or [])
        items = [
            WidgetItem(
                title=f"Exporting {j.get('name')}",
                subtitle=f"{j.get('status')} · {int(float(j.get('progress') or 0) * 100)}%",
            )
            for j in active[:3]
        ]
        items += [WidgetItem(title=f"Export failed: {j.get('name')}", subtitle=str(j.get("error") or ""), tone="critical") for j in failed[:2]]
        if not nas_ok:
            items.insert(0, WidgetItem(title="NAS export folder unavailable", tone="critical"))
        return Widget(
            title="SirisDrone",
            metrics=[
                Metric("Photos", str(photos)),
                Metric("Videos", str(videos)),
                Metric("Exporting", str(len(active)), tone="warning" if active else "neutral"),
                Metric("NAS", "OK" if nas_ok else "Offline", tone="good" if nas_ok else "critical"),
            ],
            items=items,
            empty="Nothing exporting.",
        )
