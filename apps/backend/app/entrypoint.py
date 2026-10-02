from app.main import app

from app.api.engineering_calculations import router as engineering_calculations_router
from app.api.engineering_standards import router as engineering_standards_router
from app.api.project_relationships import router as project_relationships_router
from app.api.projects import router as projects_router
from app.api.sirishydro import router as sirishydro_router
from app.hub.api import router as hub_router

# app.main owns health and sign-in. Every feature router is mounted here so
# production startup has one explicit registry, and CI can guard against
# shipping an unregistered API module (ADR 106: hub + engineering module).
for router in (
    hub_router,
    engineering_calculations_router,
    engineering_standards_router,
    sirishydro_router,
    projects_router,
    project_relationships_router,
):
    app.include_router(router)

__all__ = ["app"]
