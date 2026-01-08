"""
Configuration settings for EdgeGate.

Uses pydantic-settings to load from environment variables and .env files.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import AliasChoices, Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import sys
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    # Application
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    storage_backend: Literal["local", "s3"] = "local"
    
    # CORS - comma-separated list of allowed origins, or "*" for all
    cors_origins_str: str = Field(
        default="*",
        alias="cors_origins",
        description="Comma-separated list of allowed CORS origins, or '*' for all",
    )
    
    @computed_field
    @property
    def cors_origins(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        if self.cors_origins_str == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins_str.split(",") if origin.strip()]

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://edgegate:edgegate_dev@localhost:5432/edgegate",
        description="Async database URL (asyncpg)",
    )
    database_url_sync: str = Field(
        default="postgresql://edgegate:edgegate_dev@localhost:5432/edgegate",
        description="Sync database URL for migrations",
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("REDIS_URL", "REDISURL", "redis_url"),
        description="Redis connection URL",
    )

    @model_validator(mode="after")
    def log_settings(self) -> "Settings":
        """Log critical settings for debugging."""
        # Redact Redis URL for logging but show host
        url = self.redis_url
        raw_redis_url = os.environ.get('REDIS_URL', '')
        
        # Parse URL to show host without password
        if "@" in url:
            prefix, rest = url.split("@", 1)
            # rest should be host:port/db
            if ":" in prefix:
                base, _ = prefix.rsplit(":", 1)
                redacted = f"{base}:***@{rest}"
            else:
                redacted = f"***@{rest}"
        else:
            redacted = url
        
        print(f"DEBUG: Settings redis_url={redacted}", file=sys.stderr, flush=True)
        print(f"DEBUG: REDIS_URL env len={len(raw_redis_url)}, has_host={'@' in raw_redis_url and len(raw_redis_url.split('@')[-1]) > 1}", file=sys.stderr, flush=True)
        
        # Also log the actual broker URL being used
        print(f"DEBUG: celery_broker_url will be: {self.celery_broker_url[:20]}..." if len(self.celery_broker_url) > 20 else f"DEBUG: celery_broker_url will be: {self.celery_broker_url}", file=sys.stderr, flush=True)
        return self
    
    @computed_field
    @property
    def celery_broker_url(self) -> str:
        """Celery broker URL, defaults to redis_url."""
        return self.redis_url

    @computed_field
    @property
    def celery_result_backend(self) -> str:
        """Celery result backend, defaults to redis_url with db 1 if possible."""
        if self.redis_url.endswith("/0"):
            return self.redis_url[:-1] + "1"
        return self.redis_url

    # S3/MinIO
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_bucket_name: str = "edgegate-artifacts"
    s3_region: str = "us-east-1"

    # Security - Master Key (base64-encoded 32 bytes)
    edgegenai_master_key: str = Field(
        default="",
        description="Base64-encoded 32-byte master key for envelope encryption",
    )

    # JWT
    jwt_secret_key: str = Field(
        default="",
        description="Secret key for JWT signing (HS256)",
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # Signing Keys
    signing_keys_path: str = "./data/signing_keys"

    # Hard Limits (PRD §5)
    limit_model_upload_size_mb: int = 500
    limit_promptpack_cases: int = 50
    limit_devices_per_run: int = 5
    limit_warmup_runs: int = 1
    limit_repeats_default: int = 3
    limit_repeats_max: int = 5
    limit_max_new_tokens_default: int = 128
    limit_max_new_tokens_max: int = 256
    limit_run_timeout_default_minutes: int = 20
    limit_run_timeout_max_minutes: int = 45
    limit_workspace_concurrency: int = 1
    limit_artifact_retention_days: int = 30

    # AI Hub (optional, for integration tests)
    qaihub_api_token: Optional[str] = None

    @computed_field
    @property
    def limit_model_upload_size_bytes(self) -> int:
        """Model upload size limit in bytes."""
        return self.limit_model_upload_size_mb * 1024 * 1024

    @computed_field
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_env == "development"

    @computed_field
    @property
    def signing_keys_dir(self) -> Path:
        """Path to signing keys directory."""
        return Path(self.signing_keys_path)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
