"""
Quote Intelligence System models.

Handles parts catalog, quote generation, and historical quote lookup.
Supports parts matching, pricing automation, and version control.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean, DateTime, Enum as SQLEnum, ForeignKey, 
    Integer, Numeric, String, Text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import TenantBase

if TYPE_CHECKING:
    from models.user import User


class PartCategory(str, Enum):
    """Standard manufacturing part categories."""
    RAW_MATERIAL = "raw_material"
    COMPONENT = "component"
    ASSEMBLY = "assembly"
    FINISHED_GOOD = "finished_good"
    TOOLING = "tooling"
    CONSUMABLE = "consumable"
    SERVICE = "service"


class QuoteStatus(str, Enum):
    """Quote lifecycle status."""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class QuotePriority(str, Enum):
    """Quote priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class Part(TenantBase):
    """
    Manufacturing part catalog entry.
    
    Stores part information with support for nomenclature variations
    and automatic matching based on descriptions and attributes.
    """
    
    __tablename__ = "parts"
    
    # Part Identification
    part_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    revision: Mapped[str] = mapped_column(String(20), default="A")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    
    # Category and Classification
    category: Mapped[PartCategory] = mapped_column(
        SQLEnum(PartCategory),
        default=PartCategory.COMPONENT,
    )
    subcategory: Mapped[str | None] = mapped_column(String(100))
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    
    # Alternative Identifiers (for matching)
    alternate_part_numbers: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    manufacturer_part_numbers: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    upc_code: Mapped[str | None] = mapped_column(String(50))
    
    # Specifications
    specifications: Mapped[dict] = mapped_column(JSONB, default=dict)
    materials: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    dimensions: Mapped[dict] = mapped_column(JSONB, default=dict)
    weight: Mapped[float | None] = mapped_column(Numeric(10, 4))
    weight_unit: Mapped[str] = mapped_column(String(10), default="kg")
    
    # Pricing
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    list_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    minimum_order_qty: Mapped[int] = mapped_column(Integer, default=1)
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_obsolete: Mapped[bool] = mapped_column(Boolean, default=False)
    obsolete_date: Mapped[datetime | None] = mapped_column(DateTime)
    replacement_part_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    
    # Search Optimization (for PostgreSQL full-text search)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)
    
    # Embedding for semantic search
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Numeric), nullable=True)
    
    # Relationships
    quote_items: Mapped[list["QuoteLineItem"]] = relationship(
        "QuoteLineItem",
        back_populates="part",
    )
    similar_parts: Mapped[list["PartSimilarity"]] = relationship(
        "PartSimilarity",
        foreign_keys="PartSimilarity.part_id",
        back_populates="part",
    )
    
    __table_args__ = (
        UniqueConstraint("tenant_id", "part_number", "revision", name="uq_part_number_revision"),
    )


class PartSimilarity(TenantBase):
    """
    Pre-computed part similarity relationships.
    
    Stores similarity scores between parts for faster matching.
    """
    
    __tablename__ = "part_similarities"
    
    part_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("parts.id", ondelete="CASCADE"),
        nullable=False,
    )
    similar_part_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("parts.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Similarity Metrics
    similarity_score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    match_type: Mapped[str] = mapped_column(String(50))  # exact, fuzzy, semantic
    match_reasons: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    
    # Relationships
    part: Mapped["Part"] = relationship(
        "Part",
        foreign_keys=[part_id],
        back_populates="similar_parts",
    )
    similar_part: Mapped["Part"] = relationship(
        "Part",
        foreign_keys=[similar_part_id],
    )
    
    __table_args__ = (
        UniqueConstraint("part_id", "similar_part_id", name="uq_part_similarity"),
    )


class Customer(TenantBase):
    """
    Customer records for quote management.
    
    Stores customer information and pricing agreements.
    """
    
    __tablename__ = "customers"
    
    # Basic Information
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), index=True)
    company: Mapped[str | None] = mapped_column(String(255))
    
    # Contact
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    
    # Address
    address: Mapped[dict] = mapped_column(JSONB, default=dict)
    shipping_addresses: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    
    # Pricing
    price_tier: Mapped[str] = mapped_column(String(50), default="standard")
    discount_percentage: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    payment_terms: Mapped[str] = mapped_column(String(100), default="Net 30")
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Metadata
    notes: Mapped[str | None] = mapped_column(Text)
    custom_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Relationships
    quotes: Mapped[list["Quote"]] = relationship(
        "Quote",
        back_populates="customer",
    )


class QuoteTemplate(TenantBase):
    """
    Customizable quote templates per client.
    
    Allows different formatting, terms, and branding per customer or type.
    """
    
    __tablename__ = "quote_templates"
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    
    # Template Content
    header_content: Mapped[str | None] = mapped_column(Text)
    footer_content: Mapped[str | None] = mapped_column(Text)
    terms_and_conditions: Mapped[str | None] = mapped_column(Text)
    
    # Styling
    logo_url: Mapped[str | None] = mapped_column(String(500))
    primary_color: Mapped[str] = mapped_column(String(7), default="#1a73e8")
    font_family: Mapped[str] = mapped_column(String(100), default="Arial")
    
    # Configuration
    show_unit_prices: Mapped[bool] = mapped_column(Boolean, default=True)
    show_discounts: Mapped[bool] = mapped_column(Boolean, default=True)
    include_images: Mapped[bool] = mapped_column(Boolean, default=False)
    validity_days: Mapped[int] = mapped_column(Integer, default=30)
    
    # Status
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    quotes: Mapped[list["Quote"]] = relationship(
        "Quote",
        back_populates="template",
    )


class Quote(TenantBase):
    """
    Quote document with versioning support.
    
    Represents a formal quote with line items, pricing, and approval workflow.
    """
    
    __tablename__ = "quotes"
    
    # Quote Identification
    quote_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    reference: Mapped[str | None] = mapped_column(String(100))  # Customer PO or reference
    
    # Customer
    customer_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("customers.id"),
        nullable=False,
    )
    
    # Template
    template_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("quote_templates.id"),
    )
    
    # Status and Priority
    status: Mapped[QuoteStatus] = mapped_column(
        SQLEnum(QuoteStatus),
        default=QuoteStatus.DRAFT,
        index=True,
    )
    priority: Mapped[QuotePriority] = mapped_column(
        SQLEnum(QuotePriority),
        default=QuotePriority.NORMAL,
    )
    
    # Dates
    quote_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime)
    
    # Pricing Summary
    subtotal: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    shipping_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    
    # Terms
    payment_terms: Mapped[str | None] = mapped_column(String(100))
    delivery_terms: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    internal_notes: Mapped[str | None] = mapped_column(Text)
    
    # AI-Generated Content
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    ai_suggestions: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Workflow
    created_by_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    approved_by_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    
    # Metadata
    source: Mapped[str] = mapped_column(String(50), default="manual")  # manual, ai, import
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    custom_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Search Optimization
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)
    
    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="quotes")
    template: Mapped["QuoteTemplate | None"] = relationship("QuoteTemplate", back_populates="quotes")
    line_items: Mapped[list["QuoteLineItem"]] = relationship(
        "QuoteLineItem",
        back_populates="quote",
        cascade="all, delete-orphan",
        order_by="QuoteLineItem.line_number",
    )
    versions: Mapped[list["QuoteVersion"]] = relationship(
        "QuoteVersion",
        back_populates="quote",
        cascade="all, delete-orphan",
    )
    attachments: Mapped[list["QuoteAttachment"]] = relationship(
        "QuoteAttachment",
        back_populates="quote",
        cascade="all, delete-orphan",
    )
    
    __table_args__ = (
        UniqueConstraint("tenant_id", "quote_number", "version", name="uq_quote_number_version"),
    )


class QuoteLineItem(TenantBase):
    """
    Individual line items within a quote.
    
    Supports both catalog parts and custom items.
    """
    
    __tablename__ = "quote_line_items"
    
    quote_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("quotes.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Line Details
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    part_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("parts.id"),
    )
    
    # Custom Item (when not linked to catalog)
    custom_part_number: Mapped[str | None] = mapped_column(String(100))
    custom_description: Mapped[str | None] = mapped_column(Text)
    
    # Description Override
    description_override: Mapped[str | None] = mapped_column(Text)
    
    # Quantity and Pricing
    quantity: Mapped[float] = mapped_column(Numeric(15, 4), nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(String(20), default="EA")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    discount_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    extended_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    
    # Pricing Source
    price_source: Mapped[str] = mapped_column(String(50), default="manual")  # manual, catalog, ai
    price_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    
    # Lead Time
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    
    # Notes
    notes: Mapped[str | None] = mapped_column(Text)
    
    # Relationships
    quote: Mapped["Quote"] = relationship("Quote", back_populates="line_items")
    part: Mapped["Part | None"] = relationship("Part", back_populates="quote_items")


class QuoteVersion(TenantBase):
    """
    Version history for quotes.
    
    Stores snapshots of quote state for audit and comparison.
    """
    
    __tablename__ = "quote_versions"
    
    quote_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("quotes.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Snapshot
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    # Change Info
    change_summary: Mapped[str | None] = mapped_column(Text)
    changed_by_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    
    # Relationships
    quote: Mapped["Quote"] = relationship("Quote", back_populates="versions")


class QuoteAttachment(TenantBase):
    """
    File attachments for quotes.
    
    Supports drawings, specifications, and other supporting documents.
    """
    
    __tablename__ = "quote_attachments"
    
    quote_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("quotes.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # File Information
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50))
    file_size: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    
    # Metadata
    description: Mapped[str | None] = mapped_column(Text)
    uploaded_by_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    
    # Relationships
    quote: Mapped["Quote"] = relationship("Quote", back_populates="attachments")
