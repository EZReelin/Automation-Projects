"""Sensor model representing physical sensors attached to assets."""
import uuid
from enum import Enum
from typing import TYPE_CHECKING, Optional
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, Integer, Numeric, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .asset import Asset
    from .reading import SensorReading


class SensorType(str, Enum):
    """Types of sensors supported by FabriGuard."""
    # Vibration Sensors
    VIBRATION_TRIAXIAL = "vibration_triaxial"      # Tri-axial accelerometer
    VIBRATION_UNIAXIAL = "vibration_uniaxial"      # Single-axis accelerometer

    # Temperature Sensors
    TEMPERATURE_CONTACT = "temperature_contact"     # Contact thermocouple
    TEMPERATURE_IR = "temperature_ir"               # Infrared non-contact

    # Electrical Sensors
    CURRENT_CT = "current_ct"                       # Current transformer
    VOLTAGE = "voltage"
    POWER = "power"

    # Pressure Sensors
    PRESSURE_HYDRAULIC = "pressure_hydraulic"
    PRESSURE_PNEUMATIC = "pressure_pneumatic"

    # Flow Sensors
    FLOW_COOLANT = "flow_coolant"
    FLOW_LUBRICANT = "flow_lubricant"
    FLOW_GAS = "flow_gas"                           # For welders

    # Acoustic Sensors
    ACOUSTIC_ULTRASONIC = "acoustic_ultrasonic"

    # Environmental
    HUMIDITY = "humidity"
    AMBIENT_TEMPERATURE = "ambient_temperature"


class SensorStatus(str, Enum):
    """Operational status of a sensor."""
    ACTIVE = "active"           # Transmitting data normally
    INACTIVE = "inactive"       # Not transmitting (powered off)
    ERROR = "error"             # Hardware/communication error
    LOW_BATTERY = "low_battery" # Battery below threshold
    CALIBRATING = "calibrating" # Calibration in progress
    REPLACED = "replaced"       # Sensor has been replaced


class Sensor(Base, TimestampMixin):
    """
    Sensor represents a physical sensor device attached to an asset.

    Sensors collect data at regular intervals and transmit to the edge
    gateway for preprocessing before cloud upload.
    """
    __tablename__ = "sensors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False
    )

    # Identification
    serial_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    device_id: Mapped[str] = mapped_column(String(100), nullable=False)  # MAC address or similar
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sensor_type: Mapped[SensorType] = mapped_column(
        SQLEnum(SensorType),
        nullable=False
    )
    status: Mapped[SensorStatus] = mapped_column(
        SQLEnum(SensorStatus),
        default=SensorStatus.INACTIVE,
        nullable=False
    )

    # Hardware Details
    manufacturer: Mapped[Optional[str]] = mapped_column(String(255))
    model: Mapped[Optional[str]] = mapped_column(String(255))
    firmware_version: Mapped[Optional[str]] = mapped_column(String(50))
    hardware_version: Mapped[Optional[str]] = mapped_column(String(50))

    # Installation
    installation_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    installation_location: Mapped[Optional[str]] = mapped_column(String(255))  # "Motor housing, top"
    orientation: Mapped[Optional[str]] = mapped_column(String(100))  # "Vertical", "45-degree"

    # Communication
    communication_protocol: Mapped[str] = mapped_column(String(50), default="wifi")  # wifi, cellular, lorawan, bluetooth
    gateway_id: Mapped[Optional[str]] = mapped_column(String(100))
    last_communication: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    signal_strength: Mapped[Optional[int]] = mapped_column(Integer)  # RSSI value

    # Power
    power_source: Mapped[str] = mapped_column(String(50), default="battery")  # battery, wired, energy_harvesting
    battery_level: Mapped[Optional[int]] = mapped_column(Integer)  # Percentage
    battery_voltage: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    low_battery_threshold: Mapped[int] = mapped_column(Integer, default=20)

    # Sampling Configuration
    sampling_rate_hz: Mapped[int] = mapped_column(Integer, default=1000)  # Hz for vibration
    sampling_interval_seconds: Mapped[int] = mapped_column(Integer, default=60)  # How often to sample
    reporting_interval_seconds: Mapped[int] = mapped_column(Integer, default=300)  # How often to transmit

    # Calibration
    calibration_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    calibration_due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    calibration_factor: Mapped[float] = mapped_column(Numeric(10, 6), default=1.0)
    calibration_offset: Mapped[float] = mapped_column(Numeric(10, 6), default=0.0)

    # Measurement Range
    measurement_range_min: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    measurement_range_max: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    measurement_unit: Mapped[str] = mapped_column(String(50), nullable=False)  # g, C, PSI, mA, etc.
    measurement_precision: Mapped[Optional[int]] = mapped_column(Integer)  # Decimal places

    # Thresholds (for local edge alerting)
    threshold_warning_low: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    threshold_warning_high: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    threshold_critical_low: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    threshold_critical_high: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))

    # Additional Configuration
    config: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    asset: Mapped["Asset"] = relationship(
        "Asset",
        back_populates="sensors"
    )
    readings: Mapped[list["SensorReading"]] = relationship(
        "SensorReading",
        back_populates="sensor",
        cascade="all, delete-orphan"
    )

    @property
    def is_online(self) -> bool:
        """Check if sensor has communicated recently (within 15 minutes)."""
        if not self.last_communication:
            return False
        from datetime import timezone
        now = datetime.now(timezone.utc)
        delta = now - self.last_communication
        return delta.total_seconds() < 900  # 15 minutes

    @property
    def needs_calibration(self) -> bool:
        """Check if sensor calibration is due."""
        if not self.calibration_due_date:
            return False
        from datetime import timezone
        return datetime.now(timezone.utc) >= self.calibration_due_date

    def __repr__(self) -> str:
        return f"<Sensor(id={self.id}, serial='{self.serial_number}', type={self.sensor_type})>"
