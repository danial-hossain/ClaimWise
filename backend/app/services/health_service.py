"""Service for system health diagnostics, database checks, and readiness."""

from datetime import datetime, timezone
from app.core.config import get_settings
from app.db.session import db_manager
from app.schemas.health import HealthResponse, ReadinessResponse, ServiceComponentStatus


class HealthService:
    """Evaluates readiness of all subsystems without failing hard on unconfigured optional services."""

    @staticmethod
    def get_health() -> HealthResponse:
        """Return basic liveness check for process health."""
        settings = get_settings()
        return HealthResponse(
            status="healthy",
            app_name=settings.app_name,
            environment=settings.environment,
            version=settings.app_version,
            timestamp=datetime.now(timezone.utc),
        )

    @staticmethod
    async def get_readiness() -> ReadinessResponse:
        """Inspect all dependent subsystems and return granular readiness report."""
        settings = get_settings()
        services: dict[str, ServiceComponentStatus] = {}
        unconfigured_optional: list[str] = []

        # 1. Core API Server (Always healthy if this code executes)
        services["api_server"] = ServiceComponentStatus(
            status="healthy",
            configured=True,
            required=True,
            message="FastAPI core application server is running and accepting HTTP requests.",
        )

        # 2. Database (Supabase PostgreSQL / pgvector)
        db_check = await db_manager.check_connection()
        if db_check.get("connected"):
            db_status = "healthy"
            db_msg = "Connected to Supabase PostgreSQL database."
            if db_check.get("pgvector_detected"):
                db_msg += " pgvector extension detected."
            else:
                db_msg += " Note: pgvector extension not yet enabled."
        elif not db_check.get("configured"):
            db_status = "unconfigured"
            db_msg = db_check.get("message", "DATABASE_URL not configured. Running in decoupled mode.")
            unconfigured_optional.append("postgresql_database")
        else:
            db_status = "unreachable"
            db_msg = db_check.get("message", "Failed to reach configured PostgreSQL database.")

        services["database"] = ServiceComponentStatus(
            status=db_status,
            configured=db_check.get("configured", False),
            required=False,  # Startup permitted even when DB keys are not yet provided
            message=db_msg,
            details={"pgvector_detected": str(db_check.get("pgvector_detected", False))},
        )

        # 3. Supabase Auth
        supabase_configured = bool(
            settings.supabase_url
            and "placeholder" not in settings.supabase_url
            and settings.supabase_key
            and "placeholder" not in settings.supabase_key
        )
        if supabase_configured:
            services["supabase_auth"] = ServiceComponentStatus(
                status="configured",
                configured=True,
                required=False,
                message="Supabase authentication URL and client keys are configured.",
            )
        else:
            services["supabase_auth"] = ServiceComponentStatus(
                status="unconfigured",
                configured=False,
                required=False,
                message="SUPABASE_URL or SUPABASE_KEY not configured. Auth endpoints will operate in sandbox mode.",
            )
            unconfigured_optional.append("supabase_auth")

        # 4. Gemini AI Engine (Milestone 2 component)
        gemini_configured = bool(
            settings.gemini_api_key and "placeholder" not in settings.gemini_api_key
        )
        if gemini_configured:
            services["gemini_ai_engine"] = ServiceComponentStatus(
                status="configured",
                configured=True,
                required=False,
                message="Gemini API credentials configured for future evidence analysis.",
            )
        else:
            services["gemini_ai_engine"] = ServiceComponentStatus(
                status="unconfigured",
                configured=False,
                required=False,
                message="GEMINI_API_KEY not provided. Milestone 1 foundation active without LLM calls.",
            )
            unconfigured_optional.append("gemini_ai_engine")

        # 5. Hybrid Retrieval Engine (BM25 + BGE-M3 Vector)
        services["retrieval_engine"] = ServiceComponentStatus(
            status="staged_for_milestone_2",
            configured=False,
            required=False,
            message="BGE-M3 embeddings & BM25 hybrid indexing will be activated in Milestone 2.",
        )

        # Calculate overall status
        # If API is running, status is at least operational/partial
        is_ready = True
        overall_status = "operational" if db_check.get("connected") else "partial"

        return ReadinessResponse(
            ready=is_ready,
            status=overall_status,
            app_name=settings.app_name,
            environment=settings.environment,
            version=settings.app_version,
            services=services,
            unconfigured_optional_services=unconfigured_optional,
            timestamp=datetime.now(timezone.utc),
        )


health_service = HealthService()
