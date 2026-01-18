"""Asset model representing monitored equipment."""
import uuid
from enum import Enum
from typing import TYPE_CHECKING, Optional
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, Integer, Numeric, Text, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .organization import Organization
    from .sensor import Sensor
    from .alert import Alert
    from .prediction import Prediction
    from .work_order import WorkOrder
    from .maintenance_event import MaintenanceEvent


class AssetType(str, Enum):
    """Types of equipment supported by FabriGuard."""
    # Phase 1 - MVP
    CNC_MACHINING_CENTER = "cnc_machining_center"
    CNC_LATHE = "cnc_lathe"
    HYDRAULIC_PRESS = "hydraulic_press"
    PRESS_BRAKE = "press_brake"
    AIR_COMPRESSOR = "air_compressor"

    # Phase 2 - Expansion
    SHEAR = "shear"
    PUNCH_PRESS = "punch_press"
    MIG_WELDER = "mig_welder"
    TIG_WELDER = "tig_welder"
    COOLANT_SYSTEM = "coolant_system"
    LUBRICATION_SYSTEM = "lubrication_system"

    # Generic
    OTHER = "other"


class AssetStatus(str, Enum):
    """Health status of an asset."""
    HEALTHY = "healthy"           # Green - operating normally
    WARNING = "warning"           # Yellow - anomaly detected, monitor closely
    CRITICAL = "critical"         # Red - imminent failure predicted
    MAINTENANCE = "maintenance"   # Blue - scheduled maintenance in progress
    OFFLINE = "offline"           # Gray - no sensor data received
    DECOMMISSIONED = "decommissioned"  # Asset removed from monitoring


class Asset(Base, TimestampMixin):
    """
    Asset represents a piece of equipment being monitored.

    Each asset can have multiple sensors attached and generates
    predictions, alerts, and maintenance recommendations.
    """
    __tablename__ = "assets"

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

    # Basic Information
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_tag: Mapped[str] = mapped_column(String(100), nullable=False)  # Internal ID
    asset_type: Mapped[AssetType] = mapped_column(
        SQLEnum(AssetType),
        nullable=False
    )
    status: Mapped[AssetStatus] = mapped_column(
        SQLEnum(AssetStatus),
        default=AssetStatus.OFFLINE,
        nullable=False
    )

    # Equipment Details
    manufacturer: Mapped[Optional[str]] = mapped_column(String(255))
    model: Mapped[Optional[str]] = mapped_column(String(255))
    serial_number: Mapped[Optional[str]] = mapped_column(String(255))
    year_manufactured: Mapped[Optional[int]] = mapped_column(Integer)
    installation_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Location
    location: Mapped[Optional[str]] = mapped_column(String(255))  # "Building A, Bay 3"
    department: Mapped[Optional[str]] = mapped_column(String(100))

    # Operating Parameters (equipment-specific baselines)
    operating_hours: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    rated_capacity: Mapped[Optional[str]] = mapped_column(String(100))  # "50 ton"
    operating_parameters: Mapped[Optional[dict]] = mapped_column(JSONB)  # Equipment-specific

    # Criticality & Business Impact
    criticality_score: Mapped[int] = mapped_column(Integer, default=5)  # 1-10
    hourly_downtime_cost: Mapped[float] = mapped_column(
        Numeric(12, 2),
        default=5000.00
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # ML Model Configuration
    model_version: Mapped[str] = mapped_column(String(50), default="v1.0")
    baseline_established: Mapped[bool] = mapped_column(Boolean, default=False)
    baseline_data_points: Mapped[int] = mapped_column(Integer, default=0)
    custom_thresholds: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Maintenance Schedule
    last_maintenance_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_scheduled_maintenance: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    maintenance_interval_days: Mapped[int] = mapped_column(Integer, default=90)

    # Health Metrics (computed/cached)
    health_score: Mapped[float] = mapped_column(Numeric(5, 2), default=100.0)
    predicted_rul_days: Mapped[Optional[int]] = mapped_column(Integer)
    confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    last_reading_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Image
    image_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="assets"
    )
    sensors: Mapped[list["Sensor"]] = relationship(
        "Sensor",
        back_populates="asset",
        cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        "Alert",
        back_populates="asset",
        cascade="all, delete-orphan"
    )
    predictions: Mapped[list["Prediction"]] = relationship(
        "Prediction",
        back_populates="asset",
        cascade="all, delete-orphan"
    )
    work_orders: Mapped[list["WorkOrder"]] = relationship(
        "WorkOrder",
        back_populates="asset",
        cascade="all, delete-orphan"
    )
    maintenance_events: Mapped[list["MaintenanceEvent"]] = relationship(
        "MaintenanceEvent",
        back_populates="asset",
        cascade="all, delete-orphan"
    )

    @property
    def status_color(self) -> str:
        """Return color code for dashboard display."""
        color_map = {
            AssetStatus.HEALTHY: "green",
            AssetStatus.WARNING: "yellow",
            AssetStatus.CRITICAL: "red",
            AssetStatus.MAINTENANCE: "blue",
            AssetStatus.OFFLINE: "gray",
            AssetStatus.DECOMMISSIONED: "gray"
        }
        return color_map.get(self.status, "gray")

    def __repr__(self) -> str:
        return f"<Asset(id={self.id}, name='{self.name}', type={self.asset_type}, status={self.status})>"
