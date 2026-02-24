from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "orchestrator",
        "env": settings.app_env,
    }


@router.get("/health/ready")
def readiness_check():
    key_required = settings.app_env not in {"development", "test", "desktop"}
    checks = {
        "core_api_url": bool(settings.core_api_url),
        "internal_key_present": bool(settings.core_api_internal_key) if key_required else True,
    }
    status = "ok" if all(checks.values()) else "degraded"
    return {
        "status": status,
        "service": "orchestrator",
        "env": settings.app_env,
        "checks": checks,
        "slo_targets": {
            "availability_percent": settings.slo_chat_availability_target,
            "p95_latency_ms": settings.slo_chat_p95_latency_ms,
            "monthly_error_budget_percent": settings.error_budget_monthly_percent,
        },
    }
