"""
Pydantic schemas for API request/response validation.

Provides data transfer objects for all API endpoints.
"""

from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Any

from models.user import UserRole
from models.tenant import ServiceType, SubscriptionTier
from models.quote_intelligence import QuoteStatus, QuotePriority, PartCategory
from models.knowledge_preservation import SOPStatus, InterviewStatus, KnowledgeDomainCategory
from models.erp_copilot import ERPSystem, DocumentType, QueryCategory


# Base schemas
class BaseResponse(BaseModel):
    """Base response with timestamp."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginatedResponse(BaseModel):
    """Paginated list response."""
    items: list[Any]
    total: int
    limit: int
    offset: int


class ErrorResponse(BaseModel):
    """Error response schema."""
    detail: str
    code: str | None = None


# Auth schemas
class TokenResponse(BaseModel):
    """Authentication token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """User information response."""
    id: str
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole
    tenant_id: str | None
    is_active: bool


# Tenant schemas
class TenantResponse(BaseModel):
    """Tenant information response."""
    id: str
    name: str
    slug: str
    industry: str | None
    is_active: bool
    onboarding_completed: bool
    created_at: datetime


class SubscriptionResponse(BaseModel):
    """Subscription information response."""
    id: str
    service_type: ServiceType
    tier: SubscriptionTier
    status: str
    monthly_price: float
    start_date: datetime


# Quote schemas
class PartResponse(BaseModel):
    """Part catalog item response."""
    id: str
    part_number: str
    name: str
    description: str | None
    category: PartCategory
    unit_cost: float | None
    list_price: float | None
    tags: list[str]


class QuoteLineItemResponse(BaseModel):
    """Quote line item response."""
    line_number: int
    part_id: str | None
    custom_part_number: str | None
    quantity: float
    unit_price: float
    extended_price: float


class QuoteResponse(BaseModel):
    """Quote response with line items."""
    id: str
    quote_number: str
    version: int
    customer_id: str
    status: QuoteStatus
    priority: QuotePriority
    subtotal: float
    total_amount: float
    valid_until: datetime | None
    ai_generated: bool
    line_items: list[QuoteLineItemResponse]
    created_at: datetime


# Knowledge preservation schemas
class KnowledgeDomainResponse(BaseModel):
    """Knowledge domain response."""
    id: str
    name: str
    code: str
    category: KnowledgeDomainCategory
    completion_percentage: int


class InterviewResponse(BaseModel):
    """Interview response."""
    id: str
    title: str
    status: InterviewStatus
    scheduled_date: datetime | None
    duration_minutes: int | None
    ai_summary: str | None
    extracted_topics: list[str]


class SOPResponse(BaseModel):
    """SOP response."""
    id: str
    sop_number: str
    title: str
    version: str
    status: SOPStatus
    ai_generated: bool
    ai_confidence_score: float | None
    effective_date: datetime | None


# ERP schemas
class ERPConfigResponse(BaseModel):
    """ERP configuration response."""
    id: str
    erp_system: ERPSystem
    system_version: str | None
    enabled_modules: list[str]


class ERPDocumentResponse(BaseModel):
    """ERP document response."""
    id: str
    title: str
    document_type: DocumentType
    module: str | None
    content_summary: str | None
    is_processed: bool


class ERPQueryResponse(BaseModel):
    """ERP query response."""
    query_id: str
    response: str
    confidence: float
    sources: list[dict]
    conversation_id: str
    was_fallback: bool
    response_time_ms: int


__all__ = [
    # Base
    "BaseResponse",
    "PaginatedResponse",
    "ErrorResponse",
    # Auth
    "TokenResponse",
    "UserResponse",
    # Tenant
    "TenantResponse",
    "SubscriptionResponse",
    # Quotes
    "PartResponse",
    "QuoteLineItemResponse",
    "QuoteResponse",
    # Knowledge
    "KnowledgeDomainResponse",
    "InterviewResponse",
    "SOPResponse",
    # ERP
    "ERPConfigResponse",
    "ERPDocumentResponse",
    "ERPQueryResponse",
]
