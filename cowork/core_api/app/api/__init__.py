from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.artifacts import router as artifacts_router
from app.api.config import router as config_router
from app.api.health import router as health_router
from app.api.steps import router as steps_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(artifacts_router)
router.include_router(config_router)
router.include_router(health_router)
router.include_router(steps_router)
