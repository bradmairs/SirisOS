"""SirisLearn (FastAPI): AI-written courses with quizzes, streaks and awards
(ADR 112). Its hub routes take a read key in X-API-Key (SIRISLEARN_HUB_KEY,
the same value on both sides) and return links as paths in SirisLearn, which
are put on SIRISLEARN_PUBLIC_URL here."""

from __future__ import annotations

from typing import Any

import httpx

from app.hub.connectors.base import Connector, Metric, SearchHit, Widget, WidgetItem


class SirisLearnConnector(Connector):
    id = "sirislearn"
    name = "SirisLearn"
    category = "life"
    icon = "graduation-cap"
    description = "Courses on anything, a lesson and a quiz at a time."
    env_prefix = "SIRISLEARN"

    def credentials_present(self) -> bool:
        return bool(self.setting("HUB_KEY"))

    def missing_config(self) -> str:
        return "Set SIRISLEARN_URL and SIRISLEARN_HUB_KEY (the same key as in SirisLearn's .env)."

    def headers(self) -> dict[str, str]:
        return {"X-API-Key": self.setting("HUB_KEY")}

    def link(self, path: Any) -> str | None:
        base = self.launch_url
        return f"{base}{path}" if base and isinstance(path, str) and path.startswith("/") else None

    async def check(self, client: httpx.AsyncClient) -> str | None:
        return (await self.get_json(client, "/api/hub/v1/status")).get("version")

    async def summary(self, client: httpx.AsyncClient) -> dict[str, Any]:
        return await self.get_json(client, "/api/hub/v1/summary")

    async def widget(self, client: httpx.AsyncClient) -> Widget:
        s = await self.summary(client)
        streak, xp = s.get("streak") or {}, s.get("xp") or {}
        level, courses = s.get("level") or {}, s.get("courses") or {}
        days = int(streak.get("current") or 0)
        at_risk = bool(streak.get("at_risk"))
        goal_met = bool(xp.get("goal_met"))
        items: list[WidgetItem] = []
        nxt = s.get("continue")
        if isinstance(nxt, dict) and nxt.get("lesson_title"):
            progress = nxt.get("progress") or {}
            items.append(WidgetItem(
                title=f"Next: {nxt['lesson_title']}",
                subtitle=f"{nxt.get('course_title') or ''} · {progress.get('passed', 0)}/{progress.get('lessons', 0)} lessons",
                url=self.link(nxt.get("url")),
            ))
        if at_risk:
            items.insert(0, WidgetItem(title=f"Your {days}-day streak ends at midnight", subtitle="Finish a quiz today to keep it",
                                       url=self.link(nxt.get("url")) if isinstance(nxt, dict) else self.launch_url, tone="warning"))
        review = s.get("review") if isinstance(s.get("review"), dict) else {}
        if review.get("due"):
            due = int(review["due"])
            items.append(WidgetItem(title=f"{due} card{'s' if due != 1 else ''} to review", subtitle="Daily review",
                                    url=self.link("/review")))
        for event in (s.get("recent") or [])[:3]:
            if event.get("kind") == "achievement":
                items.append(WidgetItem(title=f"Unlocked {event.get('title')}", subtitle="Award", url=self.link(event.get("url")), tone="good"))
        return Widget(
            title="Learning",
            metrics=[
                Metric("Streak", f"{days} day{'s' if days != 1 else ''}", tone="warning" if at_risk else "good" if streak.get("today_done") else "neutral"),
                Metric("Today", f"{xp.get('today', 0)}/{xp.get('goal', 0)} XP", tone="good" if goal_met else "neutral"),
                Metric("Level", str(level.get("level", 1))),
                Metric("Courses", str(courses.get("active", 0))),
            ],
            items=items,
            empty="Nothing in progress. Start a course in SirisLearn.",
        )

    async def search(self, client: httpx.AsyncClient, query: str) -> list[SearchHit]:
        found = await self.get_json(client, "/api/hub/v1/search", params={"q": query})
        return [
            SearchHit(title=str(h.get("title")), subtitle=str(h.get("subtitle") or ""), url=self.link(h.get("url")), kind=str(h.get("kind") or ""))
            for h in found.get("hits") or []
            if h.get("title")
        ]
