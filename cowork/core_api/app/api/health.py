from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "core_api",
        "env": settings.app_env,
    }


@router.get("/health/ready")
def readiness_check():
    key_required = settings.app_env not in {"development", "test", "desktop"}
    checks = {
        "database_url": bool(settings.database_url),
        "jwt_secret_not_default": settings.jwt_secret != "change-me",
        "internal_key_present": bool(settings.internal_api_key) if key_required else True,
    }
    status = "ok" if all(checks.values()) else "degraded"
    return {
        "status": status,
        "service": "core_api",
        "env": settings.app_env,
        "checks": checks,
        "slo_targets": {
            "availability_percent": settings.slo_api_availability_target,
            "p95_latency_ms": settings.slo_api_p95_latency_ms,
            "monthly_error_budget_percent": settings.error_budget_monthly_percent,
        },
    }
