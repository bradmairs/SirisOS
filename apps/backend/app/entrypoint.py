import asyncio
from contextlib import asynccontextmanager

from app.main import app

from app.api.engineering_calculations import router as engineering_calculations_router
from app.api.engineering_calculators import router as engineering_calculators_router
from app.api.engineering_standards import router as engineering_standards_router
from app.api.project_relationships import router as project_relationships_router
from app.api.projects import router as projects_router
from app.api.sirishydro import router as sirishydro_router
from app.attention.api import router as attention_router
from app.brief.api import router as brief_router
from app.career.api import router as career_router
from app.home.api import router as home_router
from app.hub.api import router as hub_router
from app.links.api import router as links_router
from app.push import notifier as push_notifier
from app.push.api import router as push_router
from app.search.api import router as search_router

# app.main owns health and sign-in. Every feature router is mounted here so
# production startup has one explicit registry, and CI can guard against
# shipping an unregistered API module (ADR 106: hub + engineering module; ADR 108: daily brief; ADR 109: search; ADR 111: career).
for router in (
    hub_router,
    home_router,
    brief_router,
    attention_router,
    search_router,
    career_router,
    links_router,
    push_router,
    engineering_calculations_router,
    engineering_calculators_router,
    engineering_standards_router,
    sirishydro_router,
    projects_router,
    project_relationships_router,
):
    app.include_router(router)

_default_lifespan = app.router.lifespan_context


@asynccontextmanager
async def lifespan(application):
    """Starts the phone-notification loop (push/notifier.py) beside the
    default lifespan, and stops it on shutdown."""
    async with _default_lifespan(application) as state:
        task = asyncio.create_task(push_notifier.loop()) if push_notifier.enabled() else None
        try:
            yield state
        finally:
            if task:
                task.cancel()


app.router.lifespan_context = lifespan


__all__ = ["app"]
