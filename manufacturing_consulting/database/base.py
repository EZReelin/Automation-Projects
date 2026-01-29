"""
Database base configuration and session management.

Provides async database connections with proper pooling and multi-tenant support.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator
from uuid import uuid4

from sqlalchemy import MetaData, event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from config.settings import settings

# Naming convention for consistent constraint names
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """
    Base class for all database models.
    
    Provides common columns and utilities for all entities.
    """
    
    metadata = metadata
    
    # Common columns for all tables
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.id})>"


class TenantBase(Base):
    """
    Base class for multi-tenant models.
    
    Adds tenant_id column and ensures all queries are scoped to tenant.
    """
    
    __abstract__ = True
    
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        index=True,
        nullable=False,
    )


# Create async engine with connection pooling
engine = create_async_engine(
    settings.database.async_url,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    pool_pre_ping=True,
    echo=settings.debug,
)

# Async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class TenantContext:
    """Thread-local storage for current tenant context."""
    
    _current_tenant_id: str | None = None
    
    @classmethod
    def set_tenant(cls, tenant_id: str) -> None:
        """Set the current tenant context."""
        cls._current_tenant_id = tenant_id
    
    @classmethod
    def get_tenant(cls) -> str | None:
        """Get the current tenant ID."""
        return cls._current_tenant_id
    
    @classmethod
    def clear_tenant(cls) -> None:
        """Clear the current tenant context."""
        cls._current_tenant_id = None


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.
    
    Provides automatic commit/rollback and proper cleanup.
    
    Usage:
        async with get_db_session() as session:
            result = await session.execute(query)
    """
    session = async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to get database session.
    
    Usage in FastAPI:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_session)):
            ...
    """
    async with get_db_session() as session:
        yield session


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
