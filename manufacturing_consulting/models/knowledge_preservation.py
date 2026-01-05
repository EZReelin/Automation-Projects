"""
Knowledge Preservation Package models.

Handles interview-to-SOP pipeline, knowledge domain management,
and review/approval workflows for manufacturing SOPs.
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


class KnowledgeDomainCategory(str, Enum):
    """Standard knowledge domain categories for manufacturing."""
    MACHINE_OPERATION = "machine_operation"
    QUALITY_CONTROL = "quality_control"
    MAINTENANCE = "maintenance"
    SAFETY = "safety"
    ASSEMBLY = "assembly"
    INSPECTION = "inspection"
    MATERIAL_HANDLING = "material_handling"
    TOOLING = "tooling"
    PROGRAMMING = "programming"  # CNC, PLC, etc.
    TROUBLESHOOTING = "troubleshooting"
    SETUP = "setup"
    CALIBRATION = "calibration"
    OTHER = "other"


class InterviewStatus(str, Enum):
    """Interview processing status."""
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    TRANSCRIBING = "transcribing"
    TRANSCRIBED = "transcribed"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class SOPStatus(str, Enum):
    """SOP document lifecycle status."""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    IN_REVIEW = "in_review"
    REVISION_REQUESTED = "revision_requested"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    SUPERSEDED = "superseded"


class SOPPriority(str, Enum):
    """SOP priority for review queue."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class KnowledgeDomain(TenantBase):
    """
    Knowledge domain representing an area of expertise.
    
    Groups related procedures, interviews, and SOPs together.
    """
    
    __tablename__ = "knowledge_domains"
    
    # Basic Information
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    
    # Category
    category: Mapped[KnowledgeDomainCategory] = mapped_column(
        SQLEnum(KnowledgeDomainCategory),
        default=KnowledgeDomainCategory.OTHER,
    )
    subcategory: Mapped[str | None] = mapped_column(String(100))
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    
    # Related Equipment/Process
    equipment_types: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    process_areas: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    completion_percentage: Mapped[int] = mapped_column(Integer, default=0)
    
    # Ownership
    primary_sme_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))  # Subject Matter Expert
    backup_sme_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    
    # Metadata
    estimated_hours: Mapped[int | None] = mapped_column(Integer)
    actual_hours: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    
    # Relationships
    interviews: Mapped[list["Interview"]] = relationship(
        "Interview",
        back_populates="knowledge_domain",
    )
    sops: Mapped[list["SOP"]] = relationship(
        "SOP",
        back_populates="knowledge_domain",
    )
    
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_knowledge_domain_code"),
    )


class SubjectMatterExpert(TenantBase):
    """
    Subject matter expert records.
    
    Tracks employees whose knowledge is being captured.
    """
    
    __tablename__ = "subject_matter_experts"
    
    # Basic Information
    employee_id: Mapped[str | None] = mapped_column(String(50))
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    
    # Employment Details
    department: Mapped[str | None] = mapped_column(String(100))
    job_title: Mapped[str | None] = mapped_column(String(100))
    years_of_experience: Mapped[int | None] = mapped_column(Integer)
    hire_date: Mapped[datetime | None] = mapped_column(DateTime)
    
    # Retirement/Transition Info
    is_retiring: Mapped[bool] = mapped_column(Boolean, default=False)
    expected_departure_date: Mapped[datetime | None] = mapped_column(DateTime)
    knowledge_transfer_priority: Mapped[str] = mapped_column(String(20), default="normal")
    
    # Expertise Areas
    expertise_areas: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    certifications: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    equipment_expertise: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Notes
    notes: Mapped[str | None] = mapped_column(Text)
    
    # Relationships
    interviews: Mapped[list["Interview"]] = relationship(
        "Interview",
        back_populates="subject_matter_expert",
    )
    
    @property
    def full_name(self) -> str:
        """Return expert's full name."""
        return f"{self.first_name} {self.last_name}"


class Interview(TenantBase):
    """
    Interview session for knowledge capture.
    
    Tracks scheduled and completed interviews with transcript and analysis.
    """
    
    __tablename__ = "interviews"
    
    # Basic Information
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    
    # Knowledge Domain
    knowledge_domain_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("knowledge_domains.id"),
        nullable=False,
    )
    
    # Subject Matter Expert
    sme_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("subject_matter_experts.id"),
        nullable=False,
    )
    
    # Status
    status: Mapped[InterviewStatus] = mapped_column(
        SQLEnum(InterviewStatus),
        default=InterviewStatus.SCHEDULED,
    )
    
    # Schedule
    scheduled_date: Mapped[datetime | None] = mapped_column(DateTime)
    actual_start_time: Mapped[datetime | None] = mapped_column(DateTime)
    actual_end_time: Mapped[datetime | None] = mapped_column(DateTime)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    
    # Interviewer
    interviewer_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    interviewer_notes: Mapped[str | None] = mapped_column(Text)
    
    # Recording
    recording_url: Mapped[str | None] = mapped_column(String(500))
    recording_storage_path: Mapped[str | None] = mapped_column(String(500))
    
    # Transcript
    transcript_raw: Mapped[str | None] = mapped_column(Text)
    transcript_cleaned: Mapped[str | None] = mapped_column(Text)
    transcript_segments: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    
    # AI Processing
    ai_summary: Mapped[str | None] = mapped_column(Text)
    extracted_topics: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    extracted_procedures: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    key_insights: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    processing_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Quality Metrics
    audio_quality_score: Mapped[float | None] = mapped_column(Numeric(3, 2))
    content_coverage_score: Mapped[float | None] = mapped_column(Numeric(3, 2))
    
    # Interview Guide
    question_template_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    questions_asked: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    follow_up_questions: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    
    # Relationships
    knowledge_domain: Mapped["KnowledgeDomain"] = relationship(
        "KnowledgeDomain",
        back_populates="interviews",
    )
    subject_matter_expert: Mapped["SubjectMatterExpert"] = relationship(
        "SubjectMatterExpert",
        back_populates="interviews",
    )
    generated_sops: Mapped[list["SOP"]] = relationship(
        "SOP",
        back_populates="source_interview",
    )


class InterviewTemplate(TenantBase):
    """
    Interview question templates for different knowledge domains.
    
    Provides structured interview guides for consistent knowledge capture.
    """
    
    __tablename__ = "interview_templates"
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    
    # Target Domain
    target_category: Mapped[KnowledgeDomainCategory | None] = mapped_column(
        SQLEnum(KnowledgeDomainCategory),
    )
    
    # Questions
    questions: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    """
    Structure:
    [
        {
            "id": "q1",
            "question": "Describe the startup procedure...",
            "category": "procedure",
            "follow_ups": ["What safety checks...", "How do you verify..."],
            "expected_duration_minutes": 5
        }
    ]
    """
    
    # Estimated Duration
    estimated_duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class SOPTemplate(TenantBase):
    """
    SOP document templates following manufacturing best practices.
    
    Provides consistent structure for generated SOPs.
    """
    
    __tablename__ = "sop_templates"
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    
    # Target Domain
    target_category: Mapped[KnowledgeDomainCategory | None] = mapped_column(
        SQLEnum(KnowledgeDomainCategory),
    )
    
    # Template Structure
    sections: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    """
    Structure:
    [
        {
            "id": "purpose",
            "title": "Purpose",
            "required": true,
            "placeholder": "Describe the purpose of this procedure..."
        },
        {
            "id": "scope",
            "title": "Scope",
            "required": true,
            "placeholder": "Define the scope and applicability..."
        }
    ]
    """
    
    # Styling
    header_template: Mapped[str | None] = mapped_column(Text)
    footer_template: Mapped[str | None] = mapped_column(Text)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class SOP(TenantBase):
    """
    Standard Operating Procedure document.
    
    Generated from interviews with full review/approval workflow.
    """
    
    __tablename__ = "sops"
    
    # Identification
    sop_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Knowledge Domain
    knowledge_domain_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("knowledge_domains.id"),
        nullable=False,
    )
    
    # Source Interview (if AI-generated)
    source_interview_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("interviews.id"),
    )
    
    # Template Used
    template_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sop_templates.id"),
    )
    
    # Status and Priority
    status: Mapped[SOPStatus] = mapped_column(
        SQLEnum(SOPStatus),
        default=SOPStatus.DRAFT,
        index=True,
    )
    priority: Mapped[SOPPriority] = mapped_column(
        SQLEnum(SOPPriority),
        default=SOPPriority.NORMAL,
    )
    
    # Content
    content: Mapped[dict] = mapped_column(JSONB, default=dict)
    """
    Structure:
    {
        "purpose": "...",
        "scope": "...",
        "responsibilities": [...],
        "definitions": {...},
        "safety_requirements": [...],
        "equipment_needed": [...],
        "materials_needed": [...],
        "procedure_steps": [
            {
                "step_number": 1,
                "title": "...",
                "description": "...",
                "cautions": [...],
                "notes": [...],
                "images": [...]
            }
        ],
        "quality_checkpoints": [...],
        "troubleshooting": [...],
        "references": [...]
    }
    """
    
    # Plain Text Version (for search and export)
    content_plain_text: Mapped[str | None] = mapped_column(Text)
    
    # AI Generation Metadata
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    ai_model_used: Mapped[str | None] = mapped_column(String(50))
    generation_prompt: Mapped[str | None] = mapped_column(Text)
    
    # Dates
    effective_date: Mapped[datetime | None] = mapped_column(DateTime)
    review_date: Mapped[datetime | None] = mapped_column(DateTime)
    next_review_date: Mapped[datetime | None] = mapped_column(DateTime)
    sunset_date: Mapped[datetime | None] = mapped_column(DateTime)
    
    # Workflow
    created_by_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    current_reviewer_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    approved_by_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    
    # Supersedes
    supersedes_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    superseded_by_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    
    # Metadata
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    equipment_types: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    related_sops: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    
    # Search Optimization
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)
    
    # Relationships
    knowledge_domain: Mapped["KnowledgeDomain"] = relationship(
        "KnowledgeDomain",
        back_populates="sops",
    )
    source_interview: Mapped["Interview | None"] = relationship(
        "Interview",
        back_populates="generated_sops",
    )
    review_comments: Mapped[list["SOPReviewComment"]] = relationship(
        "SOPReviewComment",
        back_populates="sop",
        cascade="all, delete-orphan",
    )
    versions: Mapped[list["SOPVersion"]] = relationship(
        "SOPVersion",
        back_populates="sop",
        cascade="all, delete-orphan",
    )
    attachments: Mapped[list["SOPAttachment"]] = relationship(
        "SOPAttachment",
        back_populates="sop",
        cascade="all, delete-orphan",
    )
    
    __table_args__ = (
        UniqueConstraint("tenant_id", "sop_number", "version", name="uq_sop_number_version"),
    )


class SOPReviewComment(TenantBase):
    """
    Review comments for SOP review workflow.
    
    Supports threaded discussions and revision requests.
    """
    
    __tablename__ = "sop_review_comments"
    
    sop_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sops.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Comment Details
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    section_reference: Mapped[str | None] = mapped_column(String(100))  # Which section
    
    # Type
    comment_type: Mapped[str] = mapped_column(String(50), default="general")  # general, revision, approval
    requires_action: Mapped[bool] = mapped_column(Boolean, default=False)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Threading
    parent_comment_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    
    # Author
    author_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    
    # Resolution
    resolved_by_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    
    # Relationships
    sop: Mapped["SOP"] = relationship("SOP", back_populates="review_comments")


class SOPVersion(TenantBase):
    """
    Version history for SOPs.
    
    Tracks all changes to SOP content over time.
    """
    
    __tablename__ = "sop_versions"
    
    sop_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sops.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    version_string: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Snapshot
    content_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    # Change Info
    change_summary: Mapped[str | None] = mapped_column(Text)
    change_type: Mapped[str] = mapped_column(String(50))  # minor, major, correction
    changed_by_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    
    # Approval
    approved_by_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    
    # Relationships
    sop: Mapped["SOP"] = relationship("SOP", back_populates="versions")


class SOPAttachment(TenantBase):
    """
    Attachments for SOPs (images, diagrams, videos).
    
    Supports embedded media in SOP content.
    """
    
    __tablename__ = "sop_attachments"
    
    sop_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sops.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # File Information
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50))
    file_size: Mapped[int] = mapped_column(Integer)
    mime_type: Mapped[str | None] = mapped_column(String(100))
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    
    # Metadata
    title: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    alt_text: Mapped[str | None] = mapped_column(String(255))  # For accessibility
    
    # Reference in Content
    section_reference: Mapped[str | None] = mapped_column(String(100))
    step_reference: Mapped[int | None] = mapped_column(Integer)
    
    # Upload Info
    uploaded_by_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    
    # Relationships
    sop: Mapped["SOP"] = relationship("SOP", back_populates="attachments")
