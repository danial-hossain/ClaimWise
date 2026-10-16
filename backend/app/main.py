"""Main entry point for ClaimWise FastAPI application."""

from contextlib import asynccontextmanager
import logging
import hmac
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging_security import install_log_redaction
from app.core.exceptions import (
    ClaimWiseException,
    claimwise_exception_handler,
    global_exception_handler,
    request_validation_exception_handler,
)
from app.core.security import COOKIE_ACCESS_TOKEN_KEY, COOKIE_CSRF_TOKEN_KEY

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

    # Database stores hydrate lazily, and QA/coverage index their selected policy
    # on demand. Prewarm DB connection pool and schema in background so first user request doesn't wait.
    if settings.database_url and "placeholder" not in settings.database_url:
        async def _prewarm():
            try:
                import asyncio
                from app.db.local_store import local_store
                from app.db.session import db_manager
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, db_manager.get_sync_pool)
                await loop.run_in_executor(None, local_store.init_db)
                logger.info("Database connection pool and schema prewarmed successfully.")
            except Exception as e:
                logger.warning("Background database prewarm note: %s", type(e).__name__)

        import asyncio
        asyncio.create_task(_prewarm())

    logger.info("API startup complete; policies and retrieval indexes load on demand.")

    yield
    from app.db.session import db_manager
    await db_manager.close_pool()
    logger.info("Shutting down %s", settings.app_name)



def create_application() -> FastAPI:
    """FastAPI application factory."""
    settings = get_settings()

    install_log_redaction(settings)
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

    import re
    dev_regex = re.compile(r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$")
    is_prod = settings.environment.lower() == "production"

    # Configure CORS with strict origin validation
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=None if is_prod else r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )

    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["Cache-Control"] = "no-store"
        if get_settings().environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.middleware("http")
    async def security_and_cors_middleware(request, call_next):
        # 1. State-changing requests: Validate Origin if provided
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            origin = request.headers.get("origin")
            if origin:
                is_allowed = (
                    origin in settings.cors_origins
                    or (not is_prod and dev_regex.match(origin))
                )
                if not is_allowed:
                    return add_security_headers(JSONResponse(
                        status_code=403,
                        content={"detail": "Forbidden: Origin is not authorized."},
                    ))

            # 2. CSRF Defense for cookie-based authentication
            has_bearer = request.headers.get("authorization", "").startswith("Bearer ")
            has_access_cookie = COOKIE_ACCESS_TOKEN_KEY in request.cookies
            if has_access_cookie and not has_bearer:
                exempt_paths = {
                    f"{settings.api_v1_prefix}/auth/login",
                    f"{settings.api_v1_prefix}/auth/signup",
                    f"{settings.api_v1_prefix}/auth/demo",
                }
                if request.url.path not in exempt_paths:
                    csrf_cookie = request.cookies.get(COOKIE_CSRF_TOKEN_KEY)
                    csrf_header = request.headers.get("x-csrf-token")
                    if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_header.encode("utf-8"), csrf_cookie.encode("utf-8")):
                        return add_security_headers(JSONResponse(
                            status_code=403,
                            content={"detail": "CSRF validation failed. Missing or invalid X-CSRF-Token header."},
                        ))

        response = await call_next(request)
        response = add_security_headers(response)

        # Private Network Access: Only allow verified origins
        if request.headers.get("access-control-request-private-network"):
            origin = request.headers.get("origin")
            is_allowed = False
            if origin:
                if origin in settings.cors_origins:
                    is_allowed = True
                elif not is_prod and dev_regex.match(origin):
                    is_allowed = True
            if is_allowed:
                response.headers["Access-Control-Allow-Private-Network"] = "true"
        return response

    # Register custom exception handlers
    app.add_exception_handler(ClaimWiseException, claimwise_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)

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
