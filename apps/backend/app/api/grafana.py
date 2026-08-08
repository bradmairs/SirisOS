from fastapi import APIRouter

from app.api.engineering_standards import router as engineering_standards_router
from app.api.history import router as history_router
from app.api.infrastructure import router as infrastructure_router
from app.api.synology import router as synology_router

router = APIRouter()
router.include_router(infrastructure_router)
router.include_router(synology_router)
router.include_router(history_router)
router.include_router(engineering_standards_router)

__all__ = ["router"]
