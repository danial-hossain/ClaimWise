"""Application configuration module using pydantic-settings."""

from functools import lru_cache
import json
from typing import List, Optional, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """ClaimWise application configuration loaded from environment variables."""

    # Application details
    app_name: str = Field(default="ClaimWise API", description="Name of the application")
    app_version: str = Field(default="0.1.0", description="Semantic version of application")
    environment: str = Field(default="development", description="Current runtime environment")
    debug: bool = Field(default=True, description="Enable debug mode and verbose tracebacks")
    api_v1_prefix: str = Field(default="/api/v1", description="Prefix for API v1 routes")
    host: str = Field(default="127.0.0.1", description="Bind host address")
    port: int = Field(default=8000, description="Bind port")

    # Security & CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="List of allowed CORS origins",
    )

    # Database & Supabase (PostgreSQL with pgvector & Supabase Auth)
    database_url: Optional[str] = Field(
        default=None,
        description="PostgreSQL connection string (Supabase transaction/session pooler or direct)",
    )
    supabase_url: Optional[str] = Field(
        default=None,
        description="Public URL for Supabase project instance",
    )
    supabase_key: Optional[str] = Field(
        default=None,
        description="Supabase anonymous public API key (client-safe)",
    )
    supabase_service_role_key: Optional[str] = Field(
        default=None,
        description="Supabase service role secret key (NEVER expose to frontend)",
    )
    supabase_jwt_secret: Optional[str] = Field(
        default=None,
        description="Supabase JWT secret for validating user access tokens (HS256)",
    )
    supabase_jwt_audience: str = Field(
        default="authenticated",
        description="Expected JWT audience claim",
    )
    supabase_jwt_issuer: Optional[str] = Field(
        default=None,
        description="Expected JWT issuer claim",
    )

    # Gemini AI Engine (Milestone 3)
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Google Gemini LLM API key",
    )
    gemini_model_name: str = Field(
        default="gemini-3.8-flash",
        description="Google Gemini LLM model name (e.g. gemini-3.8-flash)",
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
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
