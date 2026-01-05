"""
Database module for the Manufacturing Consulting System.

Provides async database connections, session management,
and base model classes.
"""

from database.base import (
    Base,
    TenantBase,
    engine,
    async_session_factory,
    TenantContext,
    get_db_session,
    get_session,
    init_db,
    close_db,
)

__all__ = [
    "Base",
    "TenantBase",
    "engine",
    "async_session_factory",
    "TenantContext",
    "get_db_session",
    "get_session",
    "init_db",
    "close_db",
]
