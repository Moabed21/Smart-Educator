"""Smart-Educator FastAPI Application Entrypoint.

Orchestrates the entire backend service:
- Initializes application lifespan (startup and graceful shutdown hooks)
- Injects correlation tracing middleware (X-Request-ID) and CORS policies
- Standardizes global error contracts (HTTPException, 422 Validation, 500 Server errors)
- Serves the interactive Web Studio GUI or JSON service metadata via content negotiation
- Registers modular routers across all business domains
"""
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
    Modern FastAPI Lifespan Context Manager.
    
    EXPLANATION:
    - Replaces deprecated `@app.on_event("startup")` and `"shutdown"`.
    - Code before `yield` executes once when the server starts up.
      (Database schema migrations are managed via Alembic in production).
    - Code after `yield` executes upon SIGTERM / SIGINT graceful container shutdown,
      allowing in-flight requests and database connections to terminate cleanly.
    """
    logger.info("🚀 Starting %s v%s in %s environment...", settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT)
    yield
    logger.info("🛑 Gracefully shutting down %s...", settings.APP_NAME)


# ── Create FastAPI Application Instance ──
# docs_url="/docs" enables interactive Swagger UI; redoc_url="/redoc" enables ReDoc documentation
app = FastAPI(
    title="Smart-Educator API",
    version=settings.APP_VERSION,
    description="Automated AI-driven dataset generation, evaluation, and recommendation engine",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Correlation Middleware: Injects X-Request-ID across all requests ──
# Allows developers and logging aggregators to trace a single request across multiple services
app.add_middleware(RequestIdMiddleware)

# ── CORS Middleware: Configured from environment settings for frontend integration ──
# Controls which origins/domains can invoke the API from browser scripts
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True if settings.CORS_ORIGINS != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Standardized Global Error Contract Handlers ──
# Enforces a uniform JSON structure across all API failures: {"success": False, "error": ..., "path": ...}

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """
    Handles explicitly raised HTTPExceptions (e.g. 400 Bad Request, 404 Not Found).
    Ensures client always receives a structured error payload rather than generic plain text.
    """
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
    """
    Handles Pydantic input validation failures (HTTP 422 Unprocessable Entity).
    Triggered when an incoming request fails schema type checks, regex patterns, or field validators.
    Returns detailed field-level errors explaining which parameter failed validation.
    """
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
    """
    Catch-all handler for unexpected server exceptions (HTTP 500 Internal Server Error).
    Logs the full traceback with correlation Request ID while shielding client from sensitive internal traces.
    """
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
    Content Negotiation Endpoint:
    - If accessed by a web browser: Serves the interactive Smart-Educator Web Studio GUI (static/index.html).
    - If queried by an API client (Accept: application/json): Returns service metadata and doc links.
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
# Mounts individual domain routers under standard URL prefixes (/api/v1/...)
app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(dataset.dataset_router)
app.include_router(training_pairs.training_pairs_router)
app.include_router(recommendations_questions.rec_questions_router)

