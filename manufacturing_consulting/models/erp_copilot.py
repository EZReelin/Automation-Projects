"""
ERP Copilot models.

Handles ERP system integration, documentation indexing,
and natural language query interface.
"""

from datetime import datetime
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


class ERPSystem(str, Enum):
    """Supported ERP systems."""
    SAP = "sap"
    SAP_BUSINESS_ONE = "sap_business_one"
    ORACLE_NETSUITE = "oracle_netsuite"
    ORACLE_JD_EDWARDS = "oracle_jd_edwards"
    EPICOR = "epicor"
    SYSPRO = "syspro"
    INFOR = "infor"
    SAGE = "sage"
    MICROSOFT_DYNAMICS = "microsoft_dynamics"
    QUICKBOOKS_ENTERPRISE = "quickbooks_enterprise"
    OTHER = "other"


class DocumentType(str, Enum):
    """Types of ERP documentation."""
    USER_MANUAL = "user_manual"
    ADMIN_GUIDE = "admin_guide"
    TRAINING_MATERIAL = "training_material"
    QUICK_REFERENCE = "quick_reference"
    FAQ = "faq"
    TROUBLESHOOTING = "troubleshooting"
    PROCESS_FLOW = "process_flow"
    CONFIGURATION = "configuration"
    API_DOCUMENTATION = "api_documentation"
    RELEASE_NOTES = "release_notes"
    CUSTOM_PROCEDURE = "custom_procedure"
    VIDEO_TRANSCRIPT = "video_transcript"
    OTHER = "other"


class QueryCategory(str, Enum):
    """Categories for ERP queries."""
    HOW_TO = "how_to"
    WHERE_TO_FIND = "where_to_find"
    TROUBLESHOOTING = "troubleshooting"
    CONFIGURATION = "configuration"
    REPORTING = "reporting"
    DATA_ENTRY = "data_entry"
    WORKFLOW = "workflow"
    INTEGRATION = "integration"
    PERMISSIONS = "permissions"
    OTHER = "other"


class ERPConfiguration(TenantBase):
    """
    ERP system configuration for a tenant.
    
    Stores connection details and system-specific settings.
    """
    
    __tablename__ = "erp_configurations"
    
    # System Details
    erp_system: Mapped[ERPSystem] = mapped_column(
        SQLEnum(ERPSystem),
        nullable=False,
    )
    system_version: Mapped[str | None] = mapped_column(String(50))
    instance_name: Mapped[str | None] = mapped_column(String(100))
    
    # Connection (encrypted in practice)
    connection_type: Mapped[str] = mapped_column(String(50), default="api")  # api, database, manual
    connection_config: Mapped[dict] = mapped_column(JSONB, default=dict)  # Encrypted in production
    
    # Modules Enabled
    enabled_modules: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    """
    Common modules: inventory, purchasing, sales, manufacturing, finance, hr, crm
    """
    
    # Custom Fields/Terminology
    custom_terminology: Mapped[dict] = mapped_column(JSONB, default=dict)
    """
    Maps client-specific terms to standard ERP terms
    {"Work Order": "Production Order", "Job": "Project"}
    """
    
    # Navigation Structure
    navigation_map: Mapped[dict] = mapped_column(JSONB, default=dict)
    """
    Stores the menu structure and paths for the ERP
    {"Inventory": {"path": "Modules > Inventory", "submenus": [...]}}
    """
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime)
    
    # Relationships
    documents: Mapped[list["ERPDocument"]] = relationship(
        "ERPDocument",
        back_populates="erp_configuration",
    )
    queries: Mapped[list["ERPQuery"]] = relationship(
        "ERPQuery",
        back_populates="erp_configuration",
    )


class ERPDocument(TenantBase):
    """
    ERP documentation entry.
    
    Stores and indexes ERP documentation for semantic search.
    """
    
    __tablename__ = "erp_documents"
    
    # Configuration Link
    erp_config_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("erp_configurations.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Document Information
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(
        SQLEnum(DocumentType),
        default=DocumentType.OTHER,
    )
    
    # Source
    source_url: Mapped[str | None] = mapped_column(String(1000))
    source_file_path: Mapped[str | None] = mapped_column(String(500))
    original_filename: Mapped[str | None] = mapped_column(String(255))
    
    # Content
    content_raw: Mapped[str | None] = mapped_column(Text)
    content_cleaned: Mapped[str | None] = mapped_column(Text)
    content_summary: Mapped[str | None] = mapped_column(Text)
    
    # Metadata
    module: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(100))
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    
    # ERP-Specific
    erp_menu_path: Mapped[str | None] = mapped_column(String(500))
    erp_transaction_codes: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    erp_tables_referenced: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    
    # Version
    document_version: Mapped[str | None] = mapped_column(String(50))
    effective_date: Mapped[datetime | None] = mapped_column(DateTime)
    
    # Processing Status
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processing_error: Mapped[str | None] = mapped_column(Text)
    last_processed_at: Mapped[datetime | None] = mapped_column(DateTime)
    
    # Search Optimization
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    erp_configuration: Mapped["ERPConfiguration"] = relationship(
        "ERPConfiguration",
        back_populates="documents",
    )
    chunks: Mapped[list["ERPDocumentChunk"]] = relationship(
        "ERPDocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )


class ERPDocumentChunk(TenantBase):
    """
    Chunked document content for RAG retrieval.
    
    Stores document segments with embeddings for semantic search.
    """
    
    __tablename__ = "erp_document_chunks"
    
    document_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("erp_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Chunk Details
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    
    # Position in Original
    start_position: Mapped[int | None] = mapped_column(Integer)
    end_position: Mapped[int | None] = mapped_column(Integer)
    
    # Context
    section_title: Mapped[str | None] = mapped_column(String(255))
    parent_headers: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    
    # Embedding
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Numeric), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(50))
    
    # Metadata
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Relationships
    document: Mapped["ERPDocument"] = relationship(
        "ERPDocument",
        back_populates="chunks",
    )


class ERPQuery(TenantBase):
    """
    User query log for the ERP Copilot.
    
    Tracks all queries for analytics and learning.
    """
    
    __tablename__ = "erp_queries"
    
    # Configuration Link
    erp_config_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("erp_configurations.id"),
        nullable=False,
    )
    
    # User
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    
    # Query Details
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    query_category: Mapped[QueryCategory | None] = mapped_column(
        SQLEnum(QueryCategory),
    )
    
    # Detected Intent (AI classified)
    detected_intent: Mapped[str | None] = mapped_column(String(100))
    detected_entities: Mapped[dict] = mapped_column(JSONB, default=dict)
    """
    {"module": "inventory", "action": "create", "object": "item"}
    """
    
    # Response
    response_text: Mapped[str | None] = mapped_column(Text)
    response_sources: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    """
    [{"document_id": "...", "chunk_id": "...", "relevance_score": 0.95}]
    """
    
    # Confidence
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    was_fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    fallback_reason: Mapped[str | None] = mapped_column(String(255))
    
    # Performance
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    
    # Feedback
    user_rating: Mapped[int | None] = mapped_column(Integer)  # 1-5
    user_feedback: Mapped[str | None] = mapped_column(Text)
    was_helpful: Mapped[bool | None] = mapped_column(Boolean)
    
    # Follow-up
    is_follow_up: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_query_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    conversation_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    
    # Relationships
    erp_configuration: Mapped["ERPConfiguration"] = relationship(
        "ERPConfiguration",
        back_populates="queries",
    )


class ERPQueryTemplate(TenantBase):
    """
    Common query templates and their responses.
    
    Pre-defined answers for frequently asked questions.
    """
    
    __tablename__ = "erp_query_templates"
    
    # Template Details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    
    # Query Patterns (for matching)
    query_patterns: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    """
    ["how do I create a purchase order", "creating PO", "new purchase order"]
    """
    
    # Keywords
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    
    # Response
    response_template: Mapped[str] = mapped_column(Text, nullable=False)
    response_variables: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    """
    Variables like {menu_path}, {transaction_code} that get filled in
    """
    
    # Metadata
    category: Mapped[QueryCategory | None] = mapped_column(
        SQLEnum(QueryCategory),
    )
    module: Mapped[str | None] = mapped_column(String(100))
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)


class DocumentationGap(TenantBase):
    """
    Identified gaps in ERP documentation.
    
    Tracks queries that couldn't be answered to identify missing docs.
    """
    
    __tablename__ = "documentation_gaps"
    
    # Gap Details
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    
    # Query Evidence
    sample_queries: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    query_count: Mapped[int] = mapped_column(Integer, default=1)
    unique_users: Mapped[int] = mapped_column(Integer, default=1)
    
    # Classification
    module: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[QueryCategory | None] = mapped_column(
        SQLEnum(QueryCategory),
    )
    severity: Mapped[str] = mapped_column(String(20), default="medium")  # low, medium, high, critical
    
    # Resolution
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolution_document_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    
    # Timestamps
    first_reported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_reported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ERPUsageAnalytics(TenantBase):
    """
    Aggregated usage analytics for ERP Copilot.
    
    Daily/weekly/monthly summaries for reporting.
    """
    
    __tablename__ = "erp_usage_analytics"
    
    # Period
    period_type: Mapped[str] = mapped_column(String(20), nullable=False)  # daily, weekly, monthly
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Metrics
    total_queries: Mapped[int] = mapped_column(Integer, default=0)
    unique_users: Mapped[int] = mapped_column(Integer, default=0)
    successful_queries: Mapped[int] = mapped_column(Integer, default=0)
    fallback_queries: Mapped[int] = mapped_column(Integer, default=0)
    
    # Performance
    avg_response_time_ms: Mapped[float | None] = mapped_column(Numeric(10, 2))
    avg_confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    
    # Satisfaction
    avg_rating: Mapped[float | None] = mapped_column(Numeric(3, 2))
    positive_feedback_count: Mapped[int] = mapped_column(Integer, default=0)
    negative_feedback_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Top Categories
    top_categories: Mapped[dict] = mapped_column(JSONB, default=dict)
    """
    {"how_to": 150, "troubleshooting": 75, "where_to_find": 50}
    """
    
    # Top Modules
    top_modules: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Gap Metrics
    new_gaps_identified: Mapped[int] = mapped_column(Integer, default=0)
    gaps_resolved: Mapped[int] = mapped_column(Integer, default=0)
    
    __table_args__ = (
        UniqueConstraint("tenant_id", "period_type", "period_start", name="uq_analytics_period"),
    )
