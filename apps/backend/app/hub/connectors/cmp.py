"""CMP Capabilities Database (Express + Prisma). Bearer JWT from
POST /api/auth/login, so SirisOS logs in as Brad's own account."""

from __future__ import annotations

import httpx

from app.hub.connectors.apd_pm import SessionLoginMixin
from app.hub.connectors.base import Connector, ConnectorError, Metric, Widget, raise_for_status


class CMPConnector(SessionLoginMixin, Connector):
    id = "cmp"
    name = "CMP Capabilities"
    category = "work"
    icon = "users"
    description = "Staff capabilities, CVs and the resource planner."
    env_prefix = "CMP"

    def credentials_present(self) -> bool:
        return bool(self.setting("EMAIL") and self.setting("PASSWORD"))

    def missing_config(self) -> str:
        return "Set CMP_URL, CMP_EMAIL and CMP_PASSWORD in .env."

    async def login(self, client: httpx.AsyncClient) -> str:
        response = await client.post(
            f"{self.base_url}/api/auth/login",
            json={"email": self.setting("EMAIL"), "password": self.setting("PASSWORD")},
        )
        if response.status_code in (400, 401, 403):
            raise ConnectorError("Login rejected: check CMP_EMAIL/CMP_PASSWORD", state="degraded")
        raise_for_status(response)
        token = response.json().get("token")
        if not token:
            raise ConnectorError("Login response had no token", state="degraded")
        return token

    def session_headers(self, session: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {session}"}

    async def check(self, client: httpx.AsyncClient) -> str | None:
        await self.authed_json(client, "/api/auth/me")
        return None

    async def widget(self, client: httpx.AsyncClient) -> Widget:
        stats = await self.authed_json(client, "/api/stats/me")
        by = stats.get("byProficiency") or {}
        return Widget(
            title="My capabilities",
            metrics=[
                Metric("Skills rated", str(stats.get("totalRated", 0))),
                Metric("Advanced", str(by.get("ADVANCED", 0))),
                Metric("Projects", str(stats.get("projectCount", 0))),
            ],
        )
