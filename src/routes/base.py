"""System & Health Check Routes.

Provides observability and health monitoring endpoints:
- GET /api/v1/ - API version and environment metadata
- GET /api/v1/health - High-level process status
- GET /api/v1/health/live - Fast container liveness probe (K8s/Docker)
- GET /api/v1/health/ready - Deep readiness probe validating PostgreSQL, Redis, and ChromaDB
"""
import time
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from helpers.config import get_settings, Settings
from helpers.db import get_db
from helpers.redis_client import redis_client
from services.vector_store import VectorStoreService

base_router = APIRouter(
    prefix="/api/v1",
    tags=["system"]
)


@base_router.get("/")
async def api_info(settings: Settings = Depends(get_settings)):
    """
    General API metadata.
    
    EXPLANATION:
    - FastAPI Dependency Injection: `settings: Settings = Depends(get_settings)`
      injects the cached application settings singleton into the handler function.
    """
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@base_router.get("/health")
async def get_health(settings: Settings = Depends(get_settings)):
    """Fast liveness check indicating the application process is running."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@base_router.get("/health/live")
async def get_liveness():
    """
    Kubernetes / Docker container liveness probe.
    
    EXPLANATION:
    - Liveness vs Readiness: A liveness probe checks ONLY if the web server process
      is alive and responsive. If this fails, the container orchestrator restarts the container.
    """
    return {"status": "alive"}


@base_router.get("/health/ready")
async def get_readiness(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Comprehensive readiness probe verifying active connectivity to all 3 stateful dependencies:
    1. PostgreSQL relational database (via async SQL `SELECT 1`)
    2. Redis cache (via non-blocking PING)
    3. ChromaDB vector database (via heartbeat ping)
    
    EXPLANATION:
    - A readiness probe checks if the service can actually handle real user traffic.
    - If any dependency is down, returns HTTP 503 SERVICE UNAVAILABLE instead of HTTP 200,
      signaling load balancers and orchestrators to route traffic away until healthy.
    - Automatic Session Cleanup: `db: AsyncSession = Depends(get_db)` provides an isolated
      session per request and closes it cleanly when the request finishes.
    """
    checks = {}
    is_ready = True
    start_time = time.time()

    # 1. Check PostgreSQL connection
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = {"status": "healthy"}
    except Exception as exc:
        checks["database"] = {"status": "unhealthy", "error": str(exc)}
        is_ready = False

    # 2. Check Redis connection
    try:
        pong = await redis_client.ping()
        checks["redis"] = {"status": "healthy" if pong else "unhealthy"}
        if not pong:
            is_ready = False
    except Exception as exc:
        checks["redis"] = {"status": "unhealthy", "error": str(exc)}
        is_ready = False

    # 3. Check ChromaDB connection
    try:
        chroma_healthy = VectorStoreService().ping()
        checks["chromadb"] = {"status": "healthy" if chroma_healthy else "unhealthy"}
        if not chroma_healthy:
            is_ready = False
    except Exception as exc:
        checks["chromadb"] = {"status": "unhealthy", "error": str(exc)}
        is_ready = False

    response_payload = {
        "status": "ready" if is_ready else "degraded",
        "response_time_ms": round((time.time() - start_time) * 1000, 2),
        "dependencies": checks,
    }

    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=response_payload)