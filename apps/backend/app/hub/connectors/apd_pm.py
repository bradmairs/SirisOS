"""APD Project Management Dashboard (Express + Prisma). It authenticates with
an httpOnly cookie set by POST /api/auth/login, so SirisOS logs in as a
dedicated (ideally VIEWER) service account and replays the cookie."""

from __future__ import annotations

from datetime import date, datetime

import httpx

from app.hub.connectors.base import Connector, ConnectorError, Metric, Widget, WidgetItem, raise_for_status

COOKIE_NAME = "apd_token"
OPEN_STATUSES = {"PLANNING", "DESIGN", "TENDER", "CONSTRUCTION", "PROJECT_COMPLETION", "DEFECTS_LIABILITY"}


class SessionLoginMixin:
    """Log in lazily, retry once on 401 with a fresh session."""

    _session: str | None = None

    async def login(self, client: httpx.AsyncClient) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    def session_headers(self, session: str) -> dict[str, str]:  # pragma: no cover - overridden
        raise NotImplementedError

    async def authed_get(self, client: httpx.AsyncClient, path: str) -> httpx.Response:
        for attempt in range(2):
            if self._session is None:
                self._session = await self.login(client)
            response = await client.get(f"{self.base_url}{path}", headers=self.session_headers(self._session))  # type: ignore[attr-defined]
            if response.status_code != 401 or attempt == 1:
                return response
            self._session = None
        return response  # pragma: no cover

    async def authed_json(self, client: httpx.AsyncClient, path: str):
        response = await self.authed_get(client, path)
        raise_for_status(response)
        return response.json()


class APDPMConnector(SessionLoginMixin, Connector):
    id = "apd-pm"
    name = "Project Management"
    category = "work"
    icon = "kanban"
    description = "APD projects, tasks and registers."
    env_prefix = "APD_PM"

    def credentials_present(self) -> bool:
        return bool(self.setting("EMAIL") and self.setting("PASSWORD"))

    def missing_config(self) -> str:
        return "Set APD_PM_URL, APD_PM_EMAIL and APD_PM_PASSWORD in .env."

    async def login(self, client: httpx.AsyncClient) -> str:
        response = await client.post(
            f"{self.base_url}/api/auth/login",
            json={"email": self.setting("EMAIL"), "password": self.setting("PASSWORD")},
        )
        if response.status_code in (400, 401, 403):
            raise ConnectorError("Login rejected: check APD_PM_EMAIL/APD_PM_PASSWORD", state="degraded")
        raise_for_status(response)
        token = response.cookies.get(COOKIE_NAME)
        if not token:
            raise ConnectorError("Login succeeded but no session cookie was returned", state="degraded")
        return token

    def session_headers(self, session: str) -> dict[str, str]:
        return {"Cookie": f"{COOKIE_NAME}={session}"}

    async def check(self, client: httpx.AsyncClient) -> str | None:
        await self.authed_json(client, "/api/auth/me")
        return None

    async def widget(self, client: httpx.AsyncClient) -> Widget:
        projects = await self.authed_json(client, "/api/projects")
        upcoming = await self.authed_json(client, "/api/tasks/upcoming")
        today = date.today()
        open_projects = [p for p in projects if p.get("status") in OPEN_STATUSES]
        overdue = 0
        items: list[WidgetItem] = []
        for task in upcoming:
            due = _date(task.get("dueDate"))
            late = due is not None and due < today
            overdue += late
            if len(items) < 6:
                project = (task.get("project") or {}).get("name") or "Portfolio"
                items.append(
                    WidgetItem(
                        title=str(task.get("title")),
                        subtitle=f"{project} · {'overdue ' if late else 'due '}{due:%d %b}" if due else project,
                        tone="critical" if late else ("warning" if due and (due - today).days <= 2 else "neutral"),
                    )
                )
        return Widget(
            title="Projects",
            metrics=[
                Metric("Active projects", str(len(open_projects))),
                Metric("Due tasks", str(len(upcoming))),
                Metric("Overdue", str(overdue), tone="critical" if overdue else "good"),
            ],
            items=items,
            empty="No tasks with due dates",
        )


def _date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None
