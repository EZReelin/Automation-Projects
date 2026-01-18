"""User model for authentication and authorization."""
import uuid
from enum import Enum
from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .organization import Organization


class UserRole(str, Enum):
    """User roles for access control."""
    OWNER = "owner"           # Organization owner - full access
    ADMIN = "admin"           # Admin - can manage users and settings
    MANAGER = "manager"       # Manager - can view reports, manage work orders
    TECHNICIAN = "technician" # Maintenance tech - view assets, update work orders
    VIEWER = "viewer"         # Read-only access to dashboard


class User(Base, TimestampMixin):
    """
    User represents an individual who can access the FabriGuard platform.

    Users belong to an organization and have role-based access control.
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )

    # Authentication
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Profile
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    job_title: Mapped[Optional[str]] = mapped_column(String(100))

    # Role & Permissions
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole),
        default=UserRole.VIEWER,
        nullable=False
    )

    # Notification Preferences
    notify_email: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_sms: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_push: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_threshold: Mapped[str] = mapped_column(
        String(20),
        default="warning"  # "critical", "warning", "info"
    )

    # Session & Security
    last_login_at: Mapped[Optional[str]] = mapped_column(String(50))
    failed_login_attempts: Mapped[int] = mapped_column(default=0)
    password_reset_token: Mapped[Optional[str]] = mapped_column(String(255))
    password_reset_expires: Mapped[Optional[str]] = mapped_column(String(50))

    # Mobile Device (for push notifications)
    device_token: Mapped[Optional[str]] = mapped_column(String(500))
    device_platform: Mapped[Optional[str]] = mapped_column(String(20))  # ios, android

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="users"
    )

    @property
    def full_name(self) -> str:
        """Return user's full name."""
        return f"{self.first_name} {self.last_name}"

    def has_permission(self, required_role: UserRole) -> bool:
        """Check if user has at least the required role level."""
        role_hierarchy = {
            UserRole.OWNER: 5,
            UserRole.ADMIN: 4,
            UserRole.MANAGER: 3,
            UserRole.TECHNICIAN: 2,
            UserRole.VIEWER: 1
        }
        return role_hierarchy.get(self.role, 0) >= role_hierarchy.get(required_role, 0)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role={self.role})>"
