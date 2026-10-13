"""Main entry point for ClaimWise FastAPI application."""

from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import (
    ClaimWiseException,
    claimwise_exception_handler,
    global_exception_handler,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("claimwise")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle events."""
    settings = get_settings()
    logger.info("Starting %s v%s in %s mode", settings.app_name, settings.app_version, settings.environment)
    logger.info("Allowed CORS origins: %s", settings.cors_origins)
    logger.info("Tagline: Evidence first. If no proof, no answer.")
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_application() -> FastAPI:
    """FastAPI application factory."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "ClaimWise — Evidence-first AI Insurance Assistant backend API. "
            "Policy parsing, deterministic rules engine, claim investigation, "
            "and verifiable citation retrieval."
        ),
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register custom exception handlers
    app.add_exception_handler(ClaimWiseException, claimwise_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    # Register API v1 routes
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", tags=["System"])
    async def root():
        """Root endpoint returning basic metadata and documentation links."""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "tagline": "Evidence first. If no proof, no answer.",
            "docs": "/docs",
            "health": f"{settings.api_v1_prefix}/health",
            "ready": f"{settings.api_v1_prefix}/ready",
            "environment": settings.environment,
        }

    return app


app = create_application()
