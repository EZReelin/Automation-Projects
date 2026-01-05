"""
Tenant and organization models for multi-tenant architecture.

Supports client isolation, subscription management, and usage tracking.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from models.user import User
    from models.quote_intelligence import Quote, Part
    from models.knowledge_preservation import KnowledgeDomain
    from models.erp_copilot import ERPConfiguration


class SubscriptionTier(str, Enum):
    """Available subscription tiers."""
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    """Subscription status values."""
    ACTIVE = "active"
    TRIAL = "trial"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"


class ServiceType(str, Enum):
    """Available service types."""
    QUOTE_INTELLIGENCE = "quote_intelligence"
    KNOWLEDGE_PRESERVATION = "knowledge_preservation"
    ERP_COPILOT = "erp_copilot"


class Tenant(Base):
    """
    Tenant model representing a client organization.
    
    Each tenant is isolated with their own data, users, and service subscriptions.
    """
    
    __tablename__ = "tenants"
    
    # Basic Information
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(255))
    
    # Contact Information
    primary_contact_name: Mapped[str | None] = mapped_column(String(255))
    primary_contact_email: Mapped[str | None] = mapped_column(String(255))
    primary_contact_phone: Mapped[str | None] = mapped_column(String(50))
    
    # Address
    address_line1: Mapped[str | None] = mapped_column(String(255))
    address_line2: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(100), default="United States")
    
    # Industry Details
    industry: Mapped[str | None] = mapped_column(String(100))
    employee_count: Mapped[int | None] = mapped_column(Integer)
    annual_revenue: Mapped[str | None] = mapped_column(String(50))
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    
    # Settings
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    subscriptions: Mapped[list["TenantSubscription"]] = relationship(
        "TenantSubscription",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    api_keys: Mapped[list["TenantAPIKey"]] = relationship(
        "TenantAPIKey",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    usage_records: Mapped[list["UsageRecord"]] = relationship(
        "UsageRecord",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )


class TenantSubscription(Base):
    """
    Service subscription for a tenant.
    
    Tracks which services a tenant has access to and their billing status.
    """
    
    __tablename__ = "tenant_subscriptions"
    
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Service Details
    service_type: Mapped[ServiceType] = mapped_column(
        SQLEnum(ServiceType),
        nullable=False,
    )
    tier: Mapped[SubscriptionTier] = mapped_column(
        SQLEnum(SubscriptionTier),
        default=SubscriptionTier.STARTER,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        SQLEnum(SubscriptionStatus),
        default=SubscriptionStatus.ACTIVE,
    )
    
    # Dates
    start_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    end_date: Mapped[datetime | None] = mapped_column(DateTime)
    trial_end_date: Mapped[datetime | None] = mapped_column(DateTime)
    
    # Billing
    monthly_price: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    implementation_fee: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    billing_cycle_day: Mapped[int] = mapped_column(Integer, default=1)
    
    # Usage Limits
    usage_limits: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="subscriptions")


class TenantAPIKey(Base):
    """
    API keys for tenant integrations.
    
    Allows tenants to integrate with their own systems.
    """
    
    __tablename__ = "tenant_api_keys"
    
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    prefix: Mapped[str] = mapped_column(String(10), nullable=False)  # For identification
    
    # Permissions
    permissions: Mapped[list[str]] = mapped_column(JSONB, default=list)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    
    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="api_keys")


class UsageRecord(Base):
    """
    Usage tracking for billing and analytics.
    
    Records service usage per tenant for metered billing and insights.
    """
    
    __tablename__ = "usage_records"
    
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Usage Details
    service_type: Mapped[ServiceType] = mapped_column(
        SQLEnum(ServiceType),
        nullable=False,
    )
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_value: Mapped[float] = mapped_column(Numeric(15, 4), nullable=False)
    
    # Context
    resource_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    resource_type: Mapped[str | None] = mapped_column(String(100))
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Period
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="usage_records")
