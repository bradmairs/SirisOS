import asyncio
import os
from contextlib import asynccontextmanager

from app.main import app

from app.api.engineering_calculations import router as engineering_calculations_router
from app.api.engineering_calculators import router as engineering_calculators_router
from app.api.engineering_standards import router as engineering_standards_router
from app.api.project_relationships import router as project_relationships_router
from app.api.projects import router as projects_router
from app.api.sirishydro import router as sirishydro_router
from app.access.api import router as access_router
from app.attention.api import router as attention_router
from app.backup import service as backups
from app.backup.api import router as backup_router
from app.brief.api import router as brief_router
from app.calendar.api import router as calendar_router
from app.career.api import router as career_router
from app.home.api import router as home_router
from app.hub.api import router as hub_router
from app.links.api import router as links_router
from app.hub import history as status_history
from app.hub.service import get_hub
from app.push import notifier as push_notifier
from app.push.api import act_router as push_act_router
from app.push.api import router as push_router
from app.search.api import router as search_router
from app.siris_projects.api import router as siris_projects_router
from app.security.api import router as security_router
from app.shortcuts.api import router as shortcuts_router
from app.tasks.api import router as tasks_router
from app.wrapup.api import router as wrapup_router
from app.meetings.api import router as meetings_router
from app.email_triage.api import router as email_router
from app.review.api import router as review_router
from app.fitness.api import router as fitness_router
from app.terminal.api import router as terminal_router
from app.week.api import router as week_router

# app.main owns health and sign-in. Every feature router is mounted here so
# production startup has one explicit registry, and CI can guard against
# shipping an unregistered API module (ADR 106: hub + engineering module; ADR 108: daily brief; ADR 109: search; ADR 111: career).
for router in (
    hub_router,
    home_router,
    brief_router,
    calendar_router,
    attention_router,
    search_router,
    security_router,
    shortcuts_router,
    tasks_router,
    siris_projects_router,
    wrapup_router,
    meetings_router,
    email_router,
    review_router,
    fitness_router,
    backup_router,
    access_router,
    terminal_router,
    week_router,
    career_router,
    links_router,
    push_router,
    push_act_router,
    engineering_calculations_router,
    engineering_calculators_router,
    engineering_standards_router,
    sirishydro_router,
    projects_router,
    project_relationships_router,
):
    app.include_router(router)

def status_history_enabled() -> bool:
    return os.getenv("SIRISOS_STATUS_SAMPLER", "1") not in ("0", "false", "no")


_default_lifespan = app.router.lifespan_context


@asynccontextmanager
async def lifespan(application):
    """Starts the phone-notification loop (push/notifier.py) and the nightly
    backup (backup/service.py) beside the default lifespan, and stops them on shutdown."""
    async with _default_lifespan(application) as state:
        tasks = [asyncio.create_task(push_notifier.loop())] if push_notifier.enabled() else []
        if status_history_enabled():
            tasks.append(asyncio.create_task(status_history.sampler(get_hub)))
        if backups.enabled():
            tasks.append(asyncio.create_task(backups.loop()))
        try:
            yield state
        finally:
            for task in tasks:
                task.cancel()


app.router.lifespan_context = lifespan


__all__ = ["app"]
