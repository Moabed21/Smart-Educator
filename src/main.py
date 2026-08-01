import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from helpers.db import create_tables
from routes import base, data, dataset, training_pairs, recommendations_questions

# models must be imported so SQLAlchemy registers them before create_tables() runs
import models.learningOutcome
import models.questions
import models.questionL0Link
import models.evaluationResult

logger = logging.getLogger("server.error")

@asynccontextmanager 
async def lifespan(app: FastAPI):
    await create_tables()
    yield  # anything after yield runs on shutdown

app = FastAPI(
    title="Smart-Educator API",
    version="0.1.0",
    description="Automated AI-driven dataset generation, evaluation, and recommendation engine",
    lifespan=lifespan,
)

# ── Global Exception Middleware (Pillar 4: Standardized API Contracts) ──

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Custom handler for HTTP exceptions returning standardized JSON error contract."""
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
    """Handler for Pydantic input validation failures (HTTP 422)."""
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
    """Catch-all handler for unexpected server errors — prevents raw traceback leaks."""
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

app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(dataset.dataset_router)
app.include_router(training_pairs.training_pairs_router)
app.include_router(recommendations_questions.rec_questions_router)

