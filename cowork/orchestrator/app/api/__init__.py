from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.chat import router as chat_router
from app.api.deps import router as deps_router
from app.api.files import router as files_router

router = APIRouter()
router.include_router(health_router)
router.include_router(chat_router)
router.include_router(deps_router)
router.include_router(files_router)
