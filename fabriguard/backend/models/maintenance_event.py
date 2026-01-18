"""Maintenance Event model for historical maintenance tracking."""
import uuid
from enum import Enum
from typing import TYPE_CHECKING, Optional
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, Numeric, Text, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .asset import Asset


class MaintenanceType(str, Enum):
    """Types of maintenance activities."""
    # Planned Maintenance
    PREVENTIVE = "preventive"       # Scheduled based on time/usage
    PREDICTIVE = "predictive"       # Based on condition monitoring
    CONDITION_BASED = "condition_based"  # Based on specific conditions

    # Unplanned Maintenance
    CORRECTIVE = "corrective"       # Fix after failure detection
    EMERGENCY = "emergency"         # Urgent repair after breakdown

    # Other
    INSPECTION = "inspection"       # Regular inspection
    CALIBRATION = "calibration"     # Calibration activity
    REPLACEMENT = "replacement"     # Part/component replacement
    OVERHAUL = "overhaul"          # Major overhaul
    UPGRADE = "upgrade"            # System upgrade


class MaintenanceOutcome(str, Enum):
    """Outcome of maintenance activity."""
    SUCCESSFUL = "successful"       # Issue resolved
    PARTIAL = "partial"            # Partially resolved
    UNSUCCESSFUL = "unsuccessful"   # Issue not resolved
    DEFERRED = "deferred"          # Postponed to later date
    NOT_REQUIRED = "not_required"  # Inspection found no issues


class MaintenanceEvent(Base, TimestampMixin):
    """
    MaintenanceEvent represents a historical maintenance activity.

    This model captures all maintenance performed on assets, both
    from within FabriGuard (via work orders) and historical data
    imported from external sources. Used for:
    - Training ML models (failure patterns)
    - ROI calculations
    - Maintenance history reports
    - MTBF/MTTR calculations
    """
    __tablename__ = "maintenance_events"

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

    # Event Info
    event_number: Mapped[Optional[str]] = mapped_column(String(100))  # External reference
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    maintenance_type: Mapped[MaintenanceType] = mapped_column(
        SQLEnum(MaintenanceType),
        nullable=False
    )

    # Timing
    event_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_hours: Mapped[float] = mapped_column(Numeric(8, 2), default=0)

    # Outcome
    outcome: Mapped[MaintenanceOutcome] = mapped_column(
        SQLEnum(MaintenanceOutcome),
        default=MaintenanceOutcome.SUCCESSFUL,
        nullable=False
    )

    # Failure Details (if corrective/emergency)
    was_failure: Mapped[bool] = mapped_column(Boolean, default=False)
    failure_mode: Mapped[Optional[str]] = mapped_column(String(100))
    failure_description: Mapped[Optional[str]] = mapped_column(Text)
    failure_cause: Mapped[Optional[str]] = mapped_column(Text)
    failure_detected_by: Mapped[Optional[str]] = mapped_column(String(100))  # sensor, operator, inspection

    # Work Details
    work_performed: Mapped[Optional[str]] = mapped_column(Text)
    technician_name: Mapped[Optional[str]] = mapped_column(String(255))
    technician_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    external_vendor: Mapped[Optional[str]] = mapped_column(String(255))

    # Parts & Materials
    parts_replaced: Mapped[Optional[list]] = mapped_column(JSONB)
    parts_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    # Cost
    labor_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    vendor_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    total_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    # Downtime Impact
    caused_downtime: Mapped[bool] = mapped_column(Boolean, default=False)
    downtime_hours: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    downtime_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    production_impact: Mapped[Optional[str]] = mapped_column(Text)

    # Predictions & Alerts (if FabriGuard detected)
    was_predicted: Mapped[bool] = mapped_column(Boolean, default=False)
    prediction_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    alert_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    work_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    prediction_lead_time_hours: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))

    # For ML Training
    sensor_data_available: Mapped[bool] = mapped_column(Boolean, default=False)
    data_window_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    data_window_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    labeled_for_training: Mapped[bool] = mapped_column(Boolean, default=False)
    training_label: Mapped[Optional[str]] = mapped_column(String(100))

    # Asset State After Maintenance
    operating_hours_at_event: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    health_score_before: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    health_score_after: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    # Data Source
    source: Mapped[str] = mapped_column(String(50), default="fabriguard")  # fabriguard, import, manual
    imported_from: Mapped[Optional[str]] = mapped_column(String(255))
    external_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Attachments
    attachments: Mapped[Optional[list]] = mapped_column(JSONB)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    asset: Mapped["Asset"] = relationship(
        "Asset",
        back_populates="maintenance_events"
    )

    @property
    def total_impact_cost(self) -> float:
        """Calculate total cost including downtime impact."""
        return float((self.total_cost or 0) + (self.downtime_cost or 0))

    @property
    def was_unplanned(self) -> bool:
        """Check if this was unplanned maintenance."""
        return self.maintenance_type in [
            MaintenanceType.CORRECTIVE,
            MaintenanceType.EMERGENCY
        ]

    def __repr__(self) -> str:
        return f"<MaintenanceEvent(id={self.id}, type={self.maintenance_type}, date={self.event_date})>"
