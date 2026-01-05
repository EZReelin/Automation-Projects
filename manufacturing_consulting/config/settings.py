"""
Configuration settings for the Manufacturing Consulting System.

Uses pydantic-settings for environment variable management with validation.
Supports multi-environment deployments (development, staging, production).
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database connection configuration."""
    
    model_config = SettingsConfigDict(env_prefix="DB_")
    
    host: str = "localhost"
    port: int = 5432
    name: str = "manufacturing_consulting"
    user: str = "postgres"
    password: SecretStr = SecretStr("postgres")
    pool_size: int = 20
    max_overflow: int = 10
    
    @property
    def async_url(self) -> str:
        """Construct async database URL."""
        return (
            f"postgresql+asyncpg://{self.user}:"
            f"{self.password.get_secret_value()}@"
            f"{self.host}:{self.port}/{self.name}"
        )
    
    @property
    def sync_url(self) -> str:
        """Construct sync database URL for migrations."""
        return (
            f"postgresql://{self.user}:"
            f"{self.password.get_secret_value()}@"
            f"{self.host}:{self.port}/{self.name}"
        )


class RedisSettings(BaseSettings):
    """Redis connection configuration for caching and task queues."""
    
    model_config = SettingsConfigDict(env_prefix="REDIS_")
    
    host: str = "localhost"
    port: int = 6379
    password: SecretStr | None = None
    db: int = 0
    
    @property
    def url(self) -> str:
        """Construct Redis URL."""
        if self.password:
            return f"redis://:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class AuthSettings(BaseSettings):
    """Authentication and security configuration."""
    
    model_config = SettingsConfigDict(env_prefix="AUTH_")
    
    secret_key: SecretStr = SecretStr("your-super-secret-key-change-in-production")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    password_min_length: int = 12
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 30


class AISettings(BaseSettings):
    """AI provider configuration."""
    
    model_config = SettingsConfigDict(env_prefix="AI_")
    
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    default_model: str = "claude-3-5-sonnet-20241022"
    max_tokens: int = 4096
    temperature: float = 0.7
    embedding_model: str = "text-embedding-3-small"


class StorageSettings(BaseSettings):
    """File storage configuration."""
    
    model_config = SettingsConfigDict(env_prefix="STORAGE_")
    
    backend: Literal["local", "s3", "gcs"] = "local"
    local_path: str = "./data/uploads"
    s3_bucket: str | None = None
    s3_region: str = "us-east-1"
    max_file_size_mb: int = 50


class QuoteIntelligenceSettings(BaseSettings):
    """Quote Intelligence System specific settings."""
    
    model_config = SettingsConfigDict(env_prefix="QUOTE_")
    
    similarity_threshold: float = 0.75
    max_similar_parts: int = 10
    quote_validity_days: int = 30
    enable_auto_pricing: bool = True
    pricing_confidence_threshold: float = 0.80


class KnowledgePreservationSettings(BaseSettings):
    """Knowledge Preservation Package specific settings."""
    
    model_config = SettingsConfigDict(env_prefix="KP_")
    
    min_interview_length_minutes: int = 15
    max_sop_generation_retries: int = 3
    review_workflow_stages: int = 2
    enable_auto_categorization: bool = True


class ERPCopilotSettings(BaseSettings):
    """ERP Copilot specific settings."""
    
    model_config = SettingsConfigDict(env_prefix="ERP_")
    
    supported_systems: list[str] = ["SAP", "Oracle", "NetSuite", "Epicor", "SYSPRO"]
    query_cache_ttl_seconds: int = 3600
    max_context_chunks: int = 5
    enable_learning: bool = True


class Settings(BaseSettings):
    """Main application settings aggregating all configuration sections."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application
    app_name: str = "Manufacturing Consulting System"
    app_version: str = "1.0.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    
    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]
    
    # Logging
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"
    
    # Sub-configurations
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    ai: AISettings = Field(default_factory=AISettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    quote_intelligence: QuoteIntelligenceSettings = Field(default_factory=QuoteIntelligenceSettings)
    knowledge_preservation: KnowledgePreservationSettings = Field(default_factory=KnowledgePreservationSettings)
    erp_copilot: ERPCopilotSettings = Field(default_factory=ERPCopilotSettings)
    
    # Monitoring
    sentry_dsn: str | None = None
    enable_metrics: bool = True
    metrics_port: int = 9090


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses lru_cache to ensure settings are only loaded once.
    Clear cache with get_settings.cache_clear() if needed.
    """
    return Settings()


# Convenience export
settings = get_settings()
