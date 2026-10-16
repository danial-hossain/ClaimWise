"""Health and Readiness endpoints."""

from fastapi import APIRouter, status
from app.schemas.health import HealthResponse, ReadinessResponse
from app.services.health_service import health_service

router = APIRouter(tags=["Health & Readiness"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness check",
    description="Returns immediate 200 OK if the FastAPI server process is alive.",
)
async def get_health() -> HealthResponse:
    """Liveness probe."""
    return health_service.get_health()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness check",
    description="Checks connectivity to Neon PostgreSQL and reports subsystem readiness.",
)
async def get_readiness() -> ReadinessResponse:
    """Readiness probe checking database and optional service states."""
    return await health_service.get_readiness()
