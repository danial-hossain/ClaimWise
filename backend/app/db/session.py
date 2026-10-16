"""Database connection manager and health inspector for Neon PostgreSQL."""

import asyncio
from contextlib import asynccontextmanager, contextmanager
import logging
from typing import Any, Dict, Optional
import asyncpg
import psycopg
from psycopg_pool import ConnectionPool
from app.core.config import get_settings

logger = logging.getLogger("claimwise.db")


class DatabaseManager:
    """Manages PostgreSQL connectivity checks, connection pooling, and live connections."""

    def __init__(self):
        self._async_pool: Optional[asyncpg.Pool] = None
        self._sync_pool: Optional[ConnectionPool] = None

    async def get_pool(self) -> Optional[asyncpg.Pool]:
        """Obtain or initialize asyncpg connection pool."""
        if self._async_pool is not None and not self._async_pool._closed:
            return self._async_pool
        settings = get_settings()
        if not settings.database_url or "placeholder" in settings.database_url:
            return None
        try:
            self._async_pool = await asyncpg.create_pool(
                dsn=settings.database_url,
                min_size=1,
                max_size=10,
                ssl="require",
                timeout=10.0,
            )
            return self._async_pool
        except Exception as exc:
            logger.warning("Failed to initialize asyncpg pool: %s", type(exc).__name__)
            return None

    def get_sync_pool(self) -> ConnectionPool:
        """Obtain or initialize sync ConnectionPool."""
        if self._sync_pool is None or self._sync_pool.closed:
            settings = get_settings()
            self._sync_pool = ConnectionPool(
                settings.database_url,
                min_size=1,
                max_size=10,
                timeout=10.0,
                open=True,
            )
        return self._sync_pool

    def close_sync_pool(self) -> None:
        """Close synchronous connection pool."""
        if self._sync_pool and not self._sync_pool.closed:
            try:
                self._sync_pool.close()
            except Exception:
                pass
            self._sync_pool = None

    async def close_pool(self) -> None:
        """Close connection pools gracefully."""
        if self._async_pool and not self._async_pool._closed:
            await self._async_pool.close()
            self._async_pool = None
        self.close_sync_pool()

    async def check_connection(self) -> Dict[str, Any]:
        """
        Verify live Neon PostgreSQL database connectivity and pgvector presence.
        """
        settings = get_settings()

        if not settings.database_url or "placeholder" in settings.database_url:
            return {
                "configured": False,
                "connected": False,
                "status": "unconfigured",
                "message": "DATABASE_URL is not configured or contains placeholder values.",
                "pgvector_detected": False,
            }

        try:
            conn = await asyncio.wait_for(
                asyncpg.connect(dsn=settings.database_url, ssl="require"),
                timeout=6.0,
            )
            try:
                result = await conn.fetchval("SELECT 1;")
                vector_installed = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector');"
                )
                return {
                    "configured": True,
                    "connected": result == 1,
                    "status": "healthy" if result == 1 else "degraded",
                    "message": "Successfully connected to Neon PostgreSQL database.",
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
                "message": "Database connection attempt timed out after 6 seconds.",
                "pgvector_detected": False,
            }
        except Exception as exc:
            logger.warning("Database connection failed: %s", type(exc).__name__)
            return {
                "configured": True,
                "connected": False,
                "status": "error",
                "message": f"Database connection error: {type(exc).__name__}",
                "error_detail": "Database connection unavailable",
                "pgvector_detected": False,
            }

    async def get_connection(self) -> Optional[asyncpg.Connection]:
        """Obtain a live asyncpg database connection."""
        settings = get_settings()
        if not settings.database_url or "placeholder" in settings.database_url:
            return None
        try:
            return await asyncio.wait_for(
                asyncpg.connect(dsn=settings.database_url, ssl="require"),
                timeout=6.0,
            )
        except Exception as exc:
            logger.warning("Failed to establish live database connection: %s", type(exc).__name__)
            return None

    @contextmanager
    def sync_connection(self):
        """Provide a pooled synchronous psycopg connection."""
        pool = self.get_sync_pool()
        with pool.connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise


db_manager = DatabaseManager()
import atexit
atexit.register(db_manager.close_sync_pool)
