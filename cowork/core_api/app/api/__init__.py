from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.artifacts import router as artifacts_router
from app.api.config import router as config_router
from app.api.history import router as history_router
from app.api.health import router as health_router
from app.api.mcp import router as mcp_router
from app.api.mcp_proxy import router as mcp_proxy_router
from app.api.oauth import router as oauth_router
from app.api.providers import router as providers_router
from app.api.share import router as share_router
from app.api.snapshots import router as snapshots_router
from app.api.sessions import router as sessions_router
from app.api.steps import router as steps_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(artifacts_router)
router.include_router(config_router)
router.include_router(history_router)
router.include_router(health_router)
router.include_router(mcp_router)
router.include_router(mcp_proxy_router)
router.include_router(oauth_router)
router.include_router(providers_router)
router.include_router(share_router)
router.include_router(snapshots_router)
router.include_router(sessions_router)
router.include_router(steps_router)
