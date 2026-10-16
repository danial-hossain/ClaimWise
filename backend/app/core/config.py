"""Application configuration module using pydantic-settings."""

from functools import lru_cache
import json
from urllib.parse import parse_qs, urlsplit
from typing import List, Optional, Union
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """ClaimWise application configuration loaded from environment variables."""

    # Application details
    app_name: str = Field(default="ClaimWise API", description="Name of the application")
    app_version: str = Field(default="0.1.0", description="Semantic version of application")
    environment: str = Field(default="development", description="Current runtime environment")
    debug: bool = Field(default=False, description="Enable debug mode and verbose tracebacks")
    api_v1_prefix: str = Field(default="/api/v1", description="Prefix for API v1 routes")
    host: str = Field(default="127.0.0.1", description="Bind host address")
    port: int = Field(default=8000, description="Bind port")

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_setting(cls, value: object) -> object:
        """Accept common runtime mode values from environments that export DEBUG=release."""
        if isinstance(value, str):
            mode = value.strip().lower()
            if mode in {"release", "production", "prod", "false", "0", "no", "off", "warn", "warning", "info", "error"}:
                return False
            if mode in {"development", "dev", "debug", "true", "1", "yes", "on"}:
                return True
        return value

    # Security & CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="List of allowed CORS origins",
    )

    # PostgreSQL Database (Neon with pgvector)
    database_url: Optional[str] = Field(
        default="",
        description="PostgreSQL connection string (Neon)",
    )
    jwt_secret: str = Field(
        default="",
        description="JWT secret for cryptographic HS256 access token signing and verification",
    )
    jwt_audience: str = Field(
        default="authenticated",
        description="Expected JWT audience claim",
    )
    jwt_issuer: Optional[str] = Field(
        default="claimwise",
        description="Expected JWT issuer claim",
    )

    @model_validator(mode="after")
    def validate_secrets_and_defaults(self) -> "Settings":
        """Enforce strict configuration rules based on runtime environment."""
        self.environment = str(self.environment).strip().lower()
        if self.environment not in {"development", "test", "production"}:
            raise ValueError("ENVIRONMENT must be development, test, or production.")
        is_prod = self.environment == "production"
        if is_prod:
            if (
                not self.jwt_secret
                or len(self.jwt_secret) < 32
                or "super-secret" in self.jwt_secret
                or "dev-" in self.jwt_secret
                or "claimwise-dev" in self.jwt_secret
                or len(set(self.jwt_secret)) < 8
                or any(word in self.jwt_secret.lower() for word in ("placeholder", "change-me", "changeme", "your-secret", "super-secret", "claimwise-dev"))
            ):
                raise ValueError(
                    "Default dev JWT secret cannot be used in production. Production environment requires a strong, unique JWT_SECRET of at least 32 characters."
                )
            if not self.database_url or "placeholder" in self.database_url:
                raise ValueError("DATABASE_URL is mandatory in production mode. Production environment requires a valid, reachable DATABASE_URL.")
            database = urlsplit(self.database_url)
            if database.scheme not in {"postgresql", "postgres"} or not database.hostname or not database.password or database.password.lower() in {"password", "pass", "test"}:
                raise ValueError("Production DATABASE_URL must contain valid PostgreSQL credentials.")
            if parse_qs(database.query).get("sslmode", [None])[-1] not in {"require", "verify-ca", "verify-full"}:
                raise ValueError("Production DATABASE_URL must require TLS with sslmode=require or stronger.")
            if self.debug:
                raise ValueError("DEBUG must be false in production.")
            if not self.jwt_issuer or not self.jwt_issuer.strip() or not self.jwt_audience.strip():
                raise ValueError("JWT_ISSUER and JWT_AUDIENCE are required in production.")
            if not self.cors_origins or any(
                urlsplit(origin).scheme != "https" or not urlsplit(origin).hostname
                or urlsplit(origin).username or urlsplit(origin).password
                or urlsplit(origin).path or urlsplit(origin).query or urlsplit(origin).fragment
                or "*" in origin
                for origin in self.cors_origins
            ):
                raise ValueError("Production CORS_ORIGINS must be explicit HTTPS origins without paths or wildcards.")
        else:
            # Safe fallbacks for local development/testing when not set in .env
            if not self.jwt_secret:
                self.jwt_secret = "claimwise-dev-jwt-secret-key-32chars-min!!"
            if not self.database_url:
                self.database_url = ""
        return self

    # Backward-compatibility aliases
    @property
    def supabase_jwt_secret(self) -> str:
        return self.jwt_secret

    @supabase_jwt_secret.setter
    def supabase_jwt_secret(self, val: str) -> None:
        self.jwt_secret = val

    @property
    def supabase_jwt_audience(self) -> str:
        return self.jwt_audience

    @supabase_jwt_audience.setter
    def supabase_jwt_audience(self, val: str) -> None:
        self.jwt_audience = val

    @property
    def supabase_jwt_issuer(self) -> Optional[str]:
        return self.jwt_issuer

    @supabase_jwt_issuer.setter
    def supabase_jwt_issuer(self, val: Optional[str]) -> None:
        self.jwt_issuer = val

    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None
    supabase_service_role_key: Optional[str] = None
    local_db_path: Optional[str] = None

    # Gemini AI Engine (Milestone 3)
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Google Gemini LLM API key",
    )
    gemini_model_name: str = Field(
        default="gemini-3.1-flash-lite",
        description="Google Gemini LLM model name (e.g. gemini-3.1-flash-lite)",
    )

    # Retrieval & RRF Configuration (Milestone 3)
    retrieval_rrf_k: int = Field(
        default=60,
        description="Reciprocal Rank Fusion smoothing parameter k",
    )
    retrieval_top_k: int = Field(
        default=6,
        description="Number of top retrieved clauses passed as evidence context",
    )
    dense_embedding_dim: int = Field(
        default=1024,
        description="Dense vector dimension (1024 for BGE-M3)",
    )
    dense_embedding_provider: str = Field(
        default="bge-m3",
        description="Dense embedding provider ('bge-m3' or 'mock' for testing)",
    )

    # Document Upload & Processing (Milestone 2)
    max_upload_size_bytes: int = Field(
        default=25 * 1024 * 1024,
        description="Maximum allowed upload size in bytes (default 25 MB)",
    )
    allowed_upload_mime_types: List[str] = Field(
        default=["application/pdf"],
        description="Allowed MIME types for document uploads",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Support JSON string, comma-separated string, or Python list for CORS origins."""
        if isinstance(v, str):
            v_stripped = v.strip()
            if v_stripped.startswith("[") and v_stripped.endswith("]"):
                try:
                    parsed = json.loads(v_stripped)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
