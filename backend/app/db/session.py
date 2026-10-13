"""Database connection manager and health inspector for Supabase PostgreSQL."""

import asyncio
import logging
from typing import Any, Dict, Optional
import asyncpg
from app.core.config import get_settings

logger = logging.getLogger("claimwise.db")


class DatabaseManager:
    """Manages database connectivity checks and pool initialization."""

    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None

    async def check_connection(self) -> Dict[str, Any]:
        """
        Verify live PostgreSQL / Supabase database connectivity.
        
        Returns:
            Dict containing connection status, latency, and extension diagnostics.
            Will NOT fail silently or invent fake success if credentials are not supplied.
        """
        settings = get_settings()

        if not settings.database_url or "placeholder" in settings.database_url:
            return {
                "configured": False,
                "connected": False,
                "status": "unconfigured",
                "message": "DATABASE_URL is not configured or contains placeholder values. Live database connectivity unverified.",
                "pgvector_detected": False,
            }

        try:
            # Attempt a quick direct connection with a 4-second timeout
            conn = await asyncio.wait_for(
                asyncpg.connect(dsn=settings.database_url, ssl="require"),
                timeout=4.0,
            )
            try:
                # Test basic query execution
                result = await conn.fetchval("SELECT 1;")
                
                # Check if pgvector extension is installed
                vector_installed = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector');"
                )

                return {
                    "configured": True,
                    "connected": result == 1,
                    "status": "healthy" if result == 1 else "degraded",
                    "message": "Successfully connected to PostgreSQL database.",
                    "pgvector_detected": bool(vector_installed),
                }
            finally:
                await conn.close()

        except asyncio.TimeoutError:
            logger.warning("Database connection check timed out.")
            return {
                "configured": True,
                "connected": False,
                "status": "unreachable",
                "message": "Database connection attempt timed out after 4 seconds.",
                "pgvector_detected": False,
            }
        except Exception as exc:
            logger.warning("Database connection failed: %s", exc)
            return {
                "configured": True,
                "connected": False,
                "status": "error",
                "message": f"Database connection error: {type(exc).__name__}",
                "error_detail": str(exc),
                "pgvector_detected": False,
            }

    async def get_connection(self) -> Optional[asyncpg.Connection]:
        """Obtain a live database connection if configured and available, or None."""
        settings = get_settings()
        if not settings.database_url or "placeholder" in settings.database_url:
            return None
        try:
            return await asyncio.wait_for(
                asyncpg.connect(dsn=settings.database_url, ssl="require"),
                timeout=4.0,
            )
        except Exception as exc:
            logger.warning("Failed to establish live database connection: %s", exc)
            return None


db_manager = DatabaseManager()
