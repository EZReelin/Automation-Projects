"""
FabriGuard Configuration Settings

Uses pydantic-settings for environment variable management.
"""
from typing import List, Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "FabriGuard"
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/fabriguard"
    DATABASE_ECHO: bool = False

    # InfluxDB (Time Series)
    INFLUXDB_URL: str = "http://localhost:8086"
    INFLUXDB_TOKEN: str = "fabriguard-dev-token"
    INFLUXDB_ORG: str = "fabriguard"
    INFLUXDB_BUCKET: str = "sensor_data"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT Authentication
    SECRET_KEY: str = "your-secret-key-change-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://app.fabriguard.io"
    ]

    # AWS S3 (for raw sensor data storage)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-2"
    S3_BUCKET_RAW_DATA: str = "fabriguard-raw-sensor-data"
    S3_BUCKET_ML_MODELS: str = "fabriguard-ml-models"

    # Firebase (Push Notifications)
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None

    # Twilio (SMS Notifications)
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None

    # Email (SMTP)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: str = "alerts@fabriguard.io"

    # ML Configuration
    ML_MODEL_PATH: str = "./ml/models"
    ANOMALY_THRESHOLD: float = 0.7
    RUL_CONFIDENCE_THRESHOLD: float = 0.8
    BATCH_INFERENCE_SIZE: int = 1000

    # Alert Configuration
    ALERT_COOLDOWN_MINUTES: int = 60  # Prevent alert flooding
    MAX_ALERTS_PER_ASSET_PER_DAY: int = 10

    # Data Retention
    RAW_DATA_RETENTION_DAYS: int = 90
    AGGREGATED_DATA_RETENTION_DAYS: int = 365
    PREDICTION_RETENTION_DAYS: int = 365

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
