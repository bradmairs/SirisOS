from fastapi import APIRouter

from app.api.infrastructure import router as infrastructure_router
from app.api.synology import router as synology_router

router = APIRouter()
router.include_router(infrastructure_router)
router.include_router(synology_router)

__all__ = ["router"]
