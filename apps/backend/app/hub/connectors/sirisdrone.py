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
    description = "Crop, grade and stamp drone shots, keep a flight log, and export to the NAS."
    env_prefix = "SIRISDRONE"

    def auth(self) -> httpx.BasicAuth | None:
        user, password = self.setting("USERNAME"), self.setting("PASSWORD")
        return httpx.BasicAuth(user, password) if user and password else None

    async def get_json(self, client: httpx.AsyncClient, path: str, **kwargs):
        if (auth := self.auth()) is not None:
            kwargs.setdefault("auth", auth)
        return await super().get_json(client, path, **kwargs)

    async def _flights(self, client: httpx.AsyncClient) -> dict | None:
        """SirisDrone 1.77's flight log totals and last flight; None from an older SirisDrone."""
        try:
            data = await self.get_json(client, "/api/flights/summary")
        except Exception:  # noqa: BLE001 - before 1.77, or it's busy: the rest of the widget still shows
            return None
        return data if isinstance(data, dict) else None

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
        flights = await self._flights(client)
        flight_metrics = []
        if flights and flights.get("flights"):
            flight_metrics = [Metric("Flights", str(flights["flights"])), Metric("Hours flown", f"{float(flights.get('hours') or 0):g}")]
            last = flights.get("last") or {}
            if last.get("start"):
                when = str(last["start"])[:10]
                bits = [when, f"{last.get('minutes')} min" if last.get("minutes") is not None else "",
                        f"highest {last['max_alt_m']:g} m" if last.get("max_alt_m") is not None else "",
                        f"furthest {last['furthest_m']:,} m" if last.get("furthest_m") is not None else ""]
                items.append(WidgetItem(title=f"Last flight: {last.get('place') or 'unknown place'}", subtitle=" · ".join(b for b in bits if b),
                                        url=f"{self.launch_url}/?view=flights" if self.launch_url else None))
        return Widget(
            title="SirisDrone",
            metrics=[
                *flight_metrics,
                Metric("Photos", str(photos)),
                Metric("Videos", str(videos)),
                Metric("Exporting", str(len(active)), tone="warning" if active else "neutral"),
                Metric("NAS", "OK" if nas_ok else "Offline", tone="good" if nas_ok else "critical"),
            ],
            items=items,
            empty="Nothing exporting.",
        )
