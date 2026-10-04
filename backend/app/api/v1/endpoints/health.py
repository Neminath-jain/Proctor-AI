import time
from typing import Dict
from fastapi import APIRouter, Depends
import httpx
import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, get_current_admin
from app.models.user import User
from app.schemas.health import HealthResponse, ServiceStatus

router = APIRouter(tags=["System Health"])


@router.get(
    "/health/live",
    summary="Basic liveness probe for container orchestrator and load balancer",
)
async def liveness_probe():
    return {"status": "ok"}


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Infrastructure diagnostics and service status (Admin RBAC protected)",
    dependencies=[Depends(get_current_admin)],
)
async def health_check(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> HealthResponse:
    services: Dict[str, ServiceStatus] = {}
    overall_ok = True

    # 1. PostgreSQL Database Check
    db_start = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
        db_latency = round((time.perf_counter() - db_start) * 1000, 2)
        db_host = settings.POSTGRES_HOST
        if settings.DATABASE_URL:
            db_host = settings.ASYNC_DATABASE_URL.split("@")[-1].split("/")[0]
        services["postgres"] = ServiceStatus(
            status="healthy",
            latency_ms=db_latency,
            details=f"Connected to database on {db_host}",
        )
    except Exception as e:
        overall_ok = False
        services["postgres"] = ServiceStatus(
            status="unhealthy",
            details=str(e),
        )

    # 2. Redis Cache Check
    redis_start = time.perf_counter()
    try:
        r = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=0.3,
            socket_timeout=0.3,
        )
        await r.ping()
        await r.aclose()
        redis_latency = round((time.perf_counter() - redis_start) * 1000, 2)
        services["redis"] = ServiceStatus(
            status="healthy",
            latency_ms=redis_latency,
            details=f"Connected to {settings.REDIS_URL}",
        )
    except Exception as e:
        services["redis"] = ServiceStatus(
            status="degraded",
            details=f"Redis unreachable: {str(e)}",
        )

    # 3. ML Service Check
    ml_start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.ML_SERVICE_URL}/health")
            ml_latency = round((time.perf_counter() - ml_start) * 1000, 2)
            if resp.status_code == 200:
                services["ml_service"] = ServiceStatus(
                    status="healthy",
                    latency_ms=ml_latency,
                    details=resp.json().get("status", "ok"),
                )
            else:
                services["ml_service"] = ServiceStatus(
                    status="degraded",
                    details=f"HTTP {resp.status_code}",
                )
    except Exception as e:
        services["ml_service"] = ServiceStatus(
            status="degraded",
            details=f"ML Service offline or unreachable: {str(e)}",
        )

    # 4. Judge0 Code Engine Check
    judge0_start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.JUDGE0_API_URL}/system_info")
            j0_latency = round((time.perf_counter() - judge0_start) * 1000, 2)
            if resp.status_code == 200:
                services["judge0"] = ServiceStatus(
                    status="healthy",
                    latency_ms=j0_latency,
                    details="Judge0 API online and responsive",
                )
            else:
                services["judge0"] = ServiceStatus(
                    status="degraded",
                    details=f"HTTP {resp.status_code}",
                )
    except Exception as e:
        services["judge0"] = ServiceStatus(
            status="degraded",
            details=f"Judge0 offline or starting up: {str(e)}",
        )

    return HealthResponse(
        status="ok" if overall_ok else "error",
        version="0.1.0",
        environment=settings.ENVIRONMENT,
        services=services,
    )
