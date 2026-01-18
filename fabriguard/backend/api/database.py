"""
FabriGuard Database Configuration

Async SQLAlchemy setup for PostgreSQL and InfluxDB integration.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

from api.config import settings
from models.base import Base


# Create async engine for PostgreSQL
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    poolclass=NullPool if settings.DEBUG else None,
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        # Import all models to ensure they're registered
        from models import (
            Organization, User, Asset, Sensor, SensorReading,
            Alert, Prediction, WorkOrder, MaintenanceEvent
        )
        # Create tables
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.

    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# InfluxDB Client for time-series data
class InfluxDBConnection:
    """Manages InfluxDB connection for time-series sensor data."""

    _client: InfluxDBClient = None
    _write_api = None
    _query_api = None

    @classmethod
    def get_client(cls) -> InfluxDBClient:
        """Get or create InfluxDB client."""
        if cls._client is None:
            cls._client = InfluxDBClient(
                url=settings.INFLUXDB_URL,
                token=settings.INFLUXDB_TOKEN,
                org=settings.INFLUXDB_ORG
            )
        return cls._client

    @classmethod
    def get_write_api(cls):
        """Get write API for inserting data."""
        if cls._write_api is None:
            cls._write_api = cls.get_client().write_api(write_options=SYNCHRONOUS)
        return cls._write_api

    @classmethod
    def get_query_api(cls):
        """Get query API for reading data."""
        if cls._query_api is None:
            cls._query_api = cls.get_client().query_api()
        return cls._query_api

    @classmethod
    def close(cls):
        """Close InfluxDB connection."""
        if cls._client:
            cls._client.close()
            cls._client = None
            cls._write_api = None
            cls._query_api = None


def get_influxdb():
    """Dependency that provides InfluxDB connection."""
    return InfluxDBConnection.get_client()
