"""
User and authentication models.

Supports role-based access control with tenant-scoped permissions.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from models.tenant import Tenant


class UserRole(str, Enum):
    """User roles within a tenant."""
    OWNER = "owner"  # Full access, billing management
    ADMIN = "admin"  # Manage users, full feature access
    MANAGER = "manager"  # Approve quotes, review SOPs
    ANALYST = "analyst"  # Create quotes, generate SOPs
    VIEWER = "viewer"  # Read-only access


class SystemRole(str, Enum):
    """System-wide roles for consulting staff."""
    SUPERADMIN = "superadmin"  # Full system access
    CONSULTANT = "consultant"  # Access to all clients
    SUPPORT = "support"  # Limited support access


class User(Base):
    """
    User model supporting both tenant users and system administrators.
    
    Tenant users are scoped to a single tenant, while system users
    can access multiple tenants based on their role.
    """
    
    __tablename__ = "users"
    
    # Basic Information
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    
    # Tenant Association (null for system users)
    tenant_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )
    
    # Roles
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole),
        default=UserRole.VIEWER,
    )
    system_role: Mapped[SystemRole | None] = mapped_column(
        SQLEnum(SystemRole),
        nullable=True,
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Security
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime)
    
    # Activity
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime)
    
    # Preferences
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)
    notification_settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Relationships
    tenant: Mapped["Tenant | None"] = relationship("Tenant", back_populates="users")
    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    
    @property
    def full_name(self) -> str:
        """Return user's full name."""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_system_user(self) -> bool:
        """Check if user is a system administrator."""
        return self.system_role is not None
    
    def has_permission(self, permission: str) -> bool:
        """
        Check if user has a specific permission.
        
        Permissions are derived from role and any custom overrides.
        """
        role_permissions = ROLE_PERMISSIONS.get(self.role, set())
        custom_permissions = set(self.preferences.get("permissions", []))
        return permission in role_permissions or permission in custom_permissions


# Role-based permission mapping
ROLE_PERMISSIONS = {
    UserRole.OWNER: {
        "tenant.manage",
        "users.manage",
        "billing.manage",
        "quotes.manage",
        "quotes.approve",
        "quotes.view",
        "sops.manage",
        "sops.approve",
        "sops.view",
        "erp.manage",
        "erp.query",
        "analytics.view",
    },
    UserRole.ADMIN: {
        "users.manage",
        "quotes.manage",
        "quotes.approve",
        "quotes.view",
        "sops.manage",
        "sops.approve",
        "sops.view",
        "erp.manage",
        "erp.query",
        "analytics.view",
    },
    UserRole.MANAGER: {
        "quotes.manage",
        "quotes.approve",
        "quotes.view",
        "sops.approve",
        "sops.view",
        "erp.query",
        "analytics.view",
    },
    UserRole.ANALYST: {
        "quotes.manage",
        "quotes.view",
        "sops.manage",
        "sops.view",
        "erp.query",
    },
    UserRole.VIEWER: {
        "quotes.view",
        "sops.view",
        "erp.query",
    },
}


class UserSession(Base):
    """
    Active user sessions for session management.
    
    Tracks active sessions and allows for session revocation.
    """
    
    __tablename__ = "user_sessions"
    
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Session Details
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    refresh_token_hash: Mapped[str | None] = mapped_column(String(255))
    
    # Context
    ip_address: Mapped[str | None] = mapped_column(String(45))  # IPv6 compatible
    user_agent: Mapped[str | None] = mapped_column(Text)
    device_info: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Timestamps
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Status
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    revocation_reason: Mapped[str | None] = mapped_column(String(255))
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")


class AuditLog(Base):
    """
    Audit trail for security and compliance.
    
    Records all significant actions for audit purposes.
    """
    
    __tablename__ = "audit_logs"
    
    user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    tenant_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tenants.id", ondelete="SET NULL"),
        index=True,
    )
    
    # Action Details
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    
    # Change Details
    old_values: Mapped[dict | None] = mapped_column(JSONB)
    new_values: Mapped[dict | None] = mapped_column(JSONB)
    
    # Context
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Relationships
    user: Mapped["User | None"] = relationship("User", back_populates="audit_logs")
