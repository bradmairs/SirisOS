from app.main import app

from app.api.activity import router as activity_router
from app.api.health import router as health_router
from app.api.history import router as history_router
from app.api.infrastructure import router as infrastructure_router
from app.api.intelligence import router as intelligence_router
from app.api.knowledge import router as knowledge_router
from app.api.knowledge_context import router as knowledge_context_router
from app.api.project_relationships import router as project_relationships_router
from app.api.projects import router as projects_router
from app.api.search import router as search_router
from app.api.synology import router as synology_router

# The legacy app.main owns core auth/dashboard/homelab routes. Newer feature
# modules are mounted here so production startup has one explicit registry and
# CI can guard against silently shipping an unregistered API module.
for router in (
    activity_router,
    health_router,
    history_router,
    infrastructure_router,
    intelligence_router,
    knowledge_router,
    knowledge_context_router,
    projects_router,
    project_relationships_router,
    search_router,
    synology_router,
):
    app.include_router(router)

__all__ = ["app"]
