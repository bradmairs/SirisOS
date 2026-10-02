"""GVW Timesheet Tool (FastAPI). Its pages use per-user Basic auth, so the
hub only reads the unauthenticated /healthz."""

from __future__ import annotations

import httpx

from app.hub.connectors.base import Connector


class GVWConnector(Connector):
    id = "gvw"
    name = "GVW Timesheets"
    category = "work"
    icon = "clock"
    description = "Read CMP timesheet screenshots into the GVW workbook."
    env_prefix = "GVW"

    async def check(self, client: httpx.AsyncClient) -> str | None:
        return (await self.get_json(client, "/healthz")).get("version")
