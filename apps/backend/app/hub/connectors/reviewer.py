"""Siris Engineering Reviewer (FastAPI). Optional HTTP Basic auth."""

from __future__ import annotations

import httpx

from app.hub.connectors.base import Connector, ConnectorError, Metric, Widget, WidgetItem

SEVERE = ("critical", "major", "high")


class ReviewerConnector(Connector):
    id = "reviewer"
    name = "Engineering Reviewer"
    category = "engineering"
    icon = "clipboard-check"
    description = "Drawing pre-review: checks, AI findings, mark-ups."
    env_prefix = "REVIEWER"

    def headers(self) -> dict[str, str]:
        user, password = self.setting("USERNAME"), self.setting("PASSWORD")
        if not (user and password):
            return {}
        return {"Authorization": httpx.BasicAuth(user, password)._auth_header}

    async def check(self, client: httpx.AsyncClient) -> str | None:
        health = await self.get_json(client, "/api/health")
        if not health.get("llm_available", True):
            raise ConnectorError(
                f"Deterministic checks only: {health.get('llm_provider', 'LLM')} unavailable", state="degraded"
            )
        return health.get("llm_model")

    async def widget(self, client: httpx.AsyncClient) -> Widget:
        reviews = await self.get_json(client, "/api/reviews")
        running = sum(1 for r in reviews if r.get("status") in ("queued", "running"))
        items = []
        for review in reviews[:5]:
            counts = review.get("counts") or {}
            severe = sum(int(counts.get(k, 0)) for k in SEVERE)
            total = sum(int(v) for v in counts.values())
            items.append(
                WidgetItem(
                    title=str(review.get("name")),
                    subtitle=f"{review.get('status')} · {total} findings" + (f" ({severe} severe)" if severe else ""),
                    url=f"{self.launch_url}/#/review/{review.get('id')}" if self.launch_url else None,
                    tone="critical" if severe else "neutral",
                )
            )
        return Widget(
            title="Recent reviews",
            metrics=[Metric("Reviews", str(len(reviews))), Metric("In progress", str(running))],
            items=items,
            empty="No reviews yet",
        )
