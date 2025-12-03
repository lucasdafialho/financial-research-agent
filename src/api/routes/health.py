from datetime import datetime

from fastapi import APIRouter, Depends

from src.api.dependencies import get_services
from src.api.schemas.responses import HealthResponse

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check the health status of the API and its components",
)
async def health_check(
    services: dict = Depends(get_services),
) -> HealthResponse:
    """Check health status of all services."""
    components = {}

    if services.get("database"):
        components["database"] = await services["database"].health_check()

    if services.get("cache"):
        components["cache"] = await services["cache"].health_check()

    if services.get("vector_store"):
        components["vector_store"] = await services["vector_store"].health_check()

    all_healthy = all(components.values()) if components else True
    status = "healthy" if all_healthy else "degraded"

    return HealthResponse(
        status=status,
        version="1.0.0",
        timestamp=datetime.utcnow(),
        components=components,
    )


@router.get(
    "/ready",
    summary="Readiness Check",
    description="Check if the service is ready to accept requests",
)
async def readiness_check(
    services: dict = Depends(get_services),
) -> dict:
    """Check if service is ready."""
    ready = True
    checks = {}

    if services.get("database"):
        checks["database"] = await services["database"].health_check()
        ready = ready and checks["database"]

    return {
        "ready": ready,
        "checks": checks,
    }


@router.get(
    "/live",
    summary="Liveness Check",
    description="Check if the service is alive",
)
async def liveness_check() -> dict:
    """Simple liveness check."""
    return {"alive": True}
