from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.session import get_db_session
from app.schemas.health import HealthResponse, LiveResponse, ReadinessResponse
from app.services.health_service import HealthService


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> HealthResponse:
    service = HealthService(session, started_at_monotonic=getattr(request.app.state, "started_at_monotonic", None))
    dependencies = await service.readiness()
    status = service.overall_status(dependencies)
    return HealthResponse(
        status=status,
        environment=settings.environment,
        service="api",
        dependencies=dependencies,
    )


@router.get("/live", response_model=LiveResponse)
async def live_check() -> LiveResponse:
    return LiveResponse(status="ok", environment=settings.environment, service="api")


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> ReadinessResponse:
    service = HealthService(session, started_at_monotonic=getattr(request.app.state, "started_at_monotonic", None))
    dependencies = await service.readiness()
    status = service.overall_status(dependencies)
    return ReadinessResponse(status=status, environment=settings.environment, dependencies=dependencies)


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check_legacy(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> ReadinessResponse:
    service = HealthService(session, started_at_monotonic=getattr(request.app.state, "started_at_monotonic", None))
    dependencies = await service.readiness()
    status = service.overall_status(dependencies)
    return ReadinessResponse(status=status, environment=settings.environment, dependencies=dependencies)
