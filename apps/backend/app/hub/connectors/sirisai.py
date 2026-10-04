"""SirisAI (the system assistant) and Siris Second Brain, which SirisAI serves
at /siris/brain/*. Both authenticate with SirisAI's bearer API key."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.hub.connectors.base import Connector, ConnectorError, Metric, Widget, WidgetItem, raise_for_status


class SirisAIConnector(Connector):
    id = "sirisai"
    name = "SirisAI"
    category = "assistant"
    icon = "sparkles"
    description = "The system assistant: chat, briefing, home and HUD."
    env_prefix = "SIRISAI"

    def headers(self) -> dict[str, str]:
        key = self.setting("API_KEY")
        return {"Authorization": f"Bearer {key}"} if key else {}

    async def check(self, client: httpx.AsyncClient) -> str | None:
        status = await self.get_json(client, "/siris/status")
        if isinstance(status, dict) and not status.get("llm_provider"):
            raise ConnectorError("Running, but no LLM provider is configured", state="degraded")
        return status.get("llm_provider") if isinstance(status, dict) else None

    async def hud(self, client: httpx.AsyncClient) -> dict[str, Any]:
        return await self.get_json(client, "/siris/hud/summary")

    async def widget(self, client: httpx.AsyncClient) -> Widget:
        hud = await self.hud(client)
        metrics: list[Metric] = []
        weather = hud.get("weather") or {}
        if isinstance(weather, dict) and weather.get("temperature_c") is not None:
            metrics.append(Metric("Weather", f"{round(weather['temperature_c'])}° {weather.get('conditions') or ''}".strip()))
        parcels = hud.get("parcels")
        if isinstance(parcels, list) and parcels:
            metrics.append(Metric("Parcels", str(len(parcels))))
        brain = hud.get("brain")
        if isinstance(brain, list):
            metrics.append(Metric("Learned today", str(len(brain))))
        items = [
            WidgetItem(title=str(event.get("summary") or "Event"), subtitle=_when(event.get("start")))
            for event in (hud.get("next_events") or [])
            if isinstance(event, dict)
        ]
        return Widget(title="Today", metrics=metrics, items=items, empty="Nothing on the calendar")


class SecondBrainConnector(SirisAIConnector):
    id = "second-brain"
    name = "Second Brain"
    category = "assistant"
    icon = "brain"
    description = "Notes, knowledge and long-term memory (served by SirisAI)."

    @property
    def launch_url(self) -> str | None:
        root = self.public_url or self.base_url
        return f"{root.rstrip('/')}/brain" if root else None

    async def check(self, client: httpx.AsyncClient) -> str | None:
        response = await client.get(f"{self.base_url}/siris/brain/today", headers=self.headers())
        if response.status_code == 404:
            raise ConnectorError("SirisAI has no vault configured (SIRISAI_BRAIN_PATH)", state="degraded")
        raise_for_status(response)
        return None

    async def widget(self, client: httpx.AsyncClient) -> Widget:
        today = await self.get_json(client, "/siris/brain/today")
        items = [
            WidgetItem(title=str(item.get("title")), subtitle=str(item.get("action", "")).capitalize())
            for item in (today.get("items") or [])[:6]
        ]
        return Widget(
            title="Learned today",
            metrics=[Metric("Notes", str(len(today.get("items") or [])))],
            items=items,
            empty="Nothing new in the brain today",
        )


def _when(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    if len(value) <= 10:  # all-day event
        return parsed.strftime("%a %d %b")
    return parsed.strftime("%a %H:%M")
