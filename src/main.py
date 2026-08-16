import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from helpers.config import get_settings
from helpers.logger import RequestIdMiddleware, setup_logging
from routes import base, data, dataset, training_pairs, recommendations_questions

# ── Load application settings and initialize structured logging ──
settings = get_settings()
setup_logging(settings.LOG_LEVEL)

logger = logging.getLogger("server.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager:
    - Runs setup logic on application startup (Alembic manages migrations in production).
    - Ensures clean resource teardown upon SIGTERM / graceful container shutdown.
    """
    logger.info("🚀 Starting %s v%s in %s environment...", settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT)
    yield
    logger.info("🛑 Gracefully shutting down %s...", settings.APP_NAME)


app = FastAPI(
    title="Smart-Educator API",
    version=settings.APP_VERSION,
    description="Automated AI-driven dataset generation, evaluation, and recommendation engine",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Correlation & Contextual Middleware: Injects X-Request-ID across all requests ──
app.add_middleware(RequestIdMiddleware)

# ── CORS Middleware: Configured from environment settings for frontend integration ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True if settings.CORS_ORIGINS != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Standardized Global Error Contract Handlers ──

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Returns standardized JSON error contract for application-raised HTTPExceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code,
            "path": request.url.path,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Returns standardized JSON error contract for Pydantic input validation failures (HTTP 422)."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "Validation Error",
            "details": exc.errors(),
            "path": request.url.path,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all handler for unexpected server errors — logs trace with Request ID and prevents traceback leaks."""
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal Server Error",
            "detail": str(exc),
            "path": request.url.path,
        },
    )


# ── Interactive Web Studio UI & API Metadata Endpoints ──

@app.get("/", include_in_schema=False)
@app.get("/app", response_class=HTMLResponse, include_in_schema=False)
async def serve_web_interface(request: Request):
    """
    Serves the interactive Smart-Educator Web Studio Interface for browsers,
    or returns JSON service metadata when queried by API clients.
    """
    accept_header = request.headers.get("accept", "")
    
    # If explicitly requested as JSON or without browser accept, return API metadata
    if "application/json" in accept_header and "text/html" not in accept_header:
        return JSONResponse({
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "docs_url": "/docs",
            "health_url": "/api/v1/health",
            "readiness_url": "/api/v1/health/ready",
        })

    # Serve the rich interactive Web Studio UI
    static_html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(static_html_path):
        with open(static_html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    return HTMLResponse(content="<h1>Smart-Educator API</h1><p>Web Studio Interface loading...</p>")


# ── Register Decoupled API Routers ──
app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(dataset.dataset_router)
app.include_router(training_pairs.training_pairs_router)
app.include_router(recommendations_questions.rec_questions_router)
