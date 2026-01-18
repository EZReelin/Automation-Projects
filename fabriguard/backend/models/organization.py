"""Organization model for multi-tenant support."""
import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, Boolean, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .user import User
    from .asset import Asset


class Organization(Base, TimestampMixin):
    """
    Organization represents a metal fabrication shop customer.

    Multi-tenant support allows multiple organizations to share
    the same infrastructure while keeping data isolated.
    """
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # Contact Information
    address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(50))
    zip_code: Mapped[Optional[str]] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(100), default="USA")
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    website: Mapped[Optional[str]] = mapped_column(String(255))

    # Business Information
    industry_segment: Mapped[str] = mapped_column(
        String(100),
        default="metal_fabrication"
    )
    annual_revenue_range: Mapped[Optional[str]] = mapped_column(String(50))
    employee_count_range: Mapped[Optional[str]] = mapped_column(String(50))

    # Subscription & Billing
    subscription_tier: Mapped[str] = mapped_column(String(50), default="standard")
    max_assets: Mapped[int] = mapped_column(Integer, default=10)
    monthly_rate_per_asset: Mapped[float] = mapped_column(
        Numeric(10, 2),
        default=200.00
    )
    billing_email: Mapped[Optional[str]] = mapped_column(String(255))

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_pilot: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarded_at: Mapped[Optional[str]] = mapped_column(String(50))

    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="organization",
        cascade="all, delete-orphan"
    )
    assets: Mapped[list["Asset"]] = relationship(
        "Asset",
        back_populates="organization",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name='{self.name}')>"
