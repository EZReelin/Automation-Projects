"""Work Order model for maintenance task management."""
import uuid
from enum import Enum
from typing import TYPE_CHECKING, Optional
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, Numeric, Text, DateTime, Integer
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .asset import Asset


class WorkOrderStatus(str, Enum):
    """Status of a work order."""
    DRAFT = "draft"             # Created but not submitted
    OPEN = "open"               # Ready for assignment
    ASSIGNED = "assigned"       # Assigned to technician
    IN_PROGRESS = "in_progress" # Work has started
    ON_HOLD = "on_hold"         # Waiting for parts/resources
    COMPLETED = "completed"     # Work finished
    CANCELLED = "cancelled"     # Cancelled before completion
    VERIFIED = "verified"       # Completed and verified


class WorkOrderPriority(str, Enum):
    """Priority levels for work orders."""
    LOW = "low"             # Can wait - schedule when convenient
    MEDIUM = "medium"       # Schedule within 1-2 weeks
    HIGH = "high"           # Schedule within 1 week
    URGENT = "urgent"       # Schedule within 24-48 hours
    EMERGENCY = "emergency" # Immediate action required


class WorkOrderType(str, Enum):
    """Types of work orders."""
    PREDICTIVE = "predictive"       # Based on ML prediction
    PREVENTIVE = "preventive"       # Scheduled maintenance
    CORRECTIVE = "corrective"       # Fix after failure
    INSPECTION = "inspection"       # Check/inspect
    CALIBRATION = "calibration"     # Sensor calibration
    INSTALLATION = "installation"   # New equipment/sensor


class WorkOrder(Base, TimestampMixin):
    """
    WorkOrder represents a maintenance task to be performed.

    Work orders can be automatically generated from alerts or
    manually created by users. They track the full lifecycle
    of maintenance activities and capture cost/time data for
    ROI calculations.
    """
    __tablename__ = "work_orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True
    )

    # Work Order Info
    work_order_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    work_order_type: Mapped[WorkOrderType] = mapped_column(
        SQLEnum(WorkOrderType),
        nullable=False
    )

    # Status & Priority
    status: Mapped[WorkOrderStatus] = mapped_column(
        SQLEnum(WorkOrderStatus),
        default=WorkOrderStatus.OPEN,
        nullable=False,
        index=True
    )
    priority: Mapped[WorkOrderPriority] = mapped_column(
        SQLEnum(WorkOrderPriority),
        default=WorkOrderPriority.MEDIUM,
        nullable=False
    )

    # Source Tracking
    source_alert_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    source_prediction_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    is_auto_generated: Mapped[bool] = mapped_column(Boolean, default=False)

    # Assignment
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    assigned_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Scheduling
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    scheduled_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    scheduled_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Execution
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))

    # Work Details
    procedures: Mapped[Optional[str]] = mapped_column(Text)  # Step-by-step instructions
    safety_notes: Mapped[Optional[str]] = mapped_column(Text)
    tools_required: Mapped[Optional[list]] = mapped_column(JSONB)
    parts_required: Mapped[Optional[list]] = mapped_column(JSONB)
    skills_required: Mapped[Optional[list]] = mapped_column(JSONB)

    # Completion Details
    work_performed: Mapped[Optional[str]] = mapped_column(Text)
    findings: Mapped[Optional[str]] = mapped_column(Text)
    root_cause: Mapped[Optional[str]] = mapped_column(Text)
    parts_used: Mapped[Optional[list]] = mapped_column(JSONB)

    # Time Tracking
    estimated_hours: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    actual_hours: Mapped[float] = mapped_column(Numeric(6, 2), default=0)

    # Cost Tracking (for ROI calculation)
    estimated_labor_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    actual_labor_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    parts_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    external_service_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    total_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    # Downtime Tracking
    downtime_hours: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    downtime_avoided: Mapped[bool] = mapped_column(Boolean, default=False)
    estimated_downtime_avoided_hours: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    estimated_cost_avoided: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    # Verification
    verified_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    verification_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Attachments & Media
    attachments: Mapped[Optional[list]] = mapped_column(JSONB)  # File URLs
    before_photos: Mapped[Optional[list]] = mapped_column(JSONB)
    after_photos: Mapped[Optional[list]] = mapped_column(JSONB)

    # Notes & Comments
    notes: Mapped[Optional[str]] = mapped_column(Text)
    comments: Mapped[Optional[list]] = mapped_column(JSONB)

    # Relationships
    asset: Mapped["Asset"] = relationship(
        "Asset",
        back_populates="work_orders"
    )

    @property
    def total_actual_cost(self) -> float:
        """Calculate total actual cost."""
        return float(
            (self.actual_labor_cost or 0) +
            (self.parts_cost or 0) +
            (self.external_service_cost or 0)
        )

    @property
    def is_overdue(self) -> bool:
        """Check if work order is past due date."""
        if not self.due_date:
            return False
        if self.status in [WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED, WorkOrderStatus.VERIFIED]:
            return False
        from datetime import timezone
        return datetime.now(timezone.utc) > self.due_date

    @property
    def roi_value(self) -> float:
        """Calculate ROI value (cost avoided minus actual cost)."""
        return float((self.estimated_cost_avoided or 0) - self.total_actual_cost)

    def __repr__(self) -> str:
        return f"<WorkOrder(id={self.id}, number='{self.work_order_number}', status={self.status})>"
