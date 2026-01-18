"""Sensor Reading model for time-series data storage."""
import uuid
from typing import TYPE_CHECKING, Optional
from datetime import datetime
from sqlalchemy import String, ForeignKey, Numeric, DateTime, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .sensor import Sensor


class SensorReading(Base):
    """
    SensorReading represents a single data point from a sensor.

    Note: For high-volume production use, these readings should be stored
    in a dedicated time-series database (InfluxDB/TimescaleDB) rather than
    PostgreSQL. This model serves as the schema definition and for
    lower-volume scenarios.

    Time-series data is partitioned by time for efficient querying and
    automated retention policies.
    """
    __tablename__ = "sensor_readings"

    # Composite primary key for time-series efficiency
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    sensor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sensors.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Timestamp (indexed for range queries)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    # Primary measurement value
    value: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)

    # For multi-axis sensors (e.g., tri-axial accelerometer)
    value_x: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))
    value_y: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))
    value_z: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))

    # Statistical aggregates (computed at edge for efficiency)
    value_min: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))
    value_max: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))
    value_avg: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))
    value_rms: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))  # Root Mean Square
    value_std: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))  # Standard Deviation
    sample_count: Mapped[int] = mapped_column(Integer, default=1)

    # Frequency domain features (for vibration)
    peak_frequency_hz: Mapped[Optional[float]] = mapped_column(Numeric(12, 4))
    dominant_frequencies: Mapped[Optional[dict]] = mapped_column(JSONB)  # Top N frequencies

    # Data quality
    quality_score: Mapped[float] = mapped_column(Numeric(5, 4), default=1.0)  # 0-1
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    anomaly_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))  # 0-1, from edge

    # Edge processing metadata
    edge_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    edge_gateway_id: Mapped[Optional[str]] = mapped_column(String(100))
    raw_data_reference: Mapped[Optional[str]] = mapped_column(String(500))  # S3 key for raw data

    # Additional features extracted at edge or cloud
    features: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    sensor: Mapped["Sensor"] = relationship(
        "Sensor",
        back_populates="readings"
    )

    def __repr__(self) -> str:
        return f"<SensorReading(sensor_id={self.sensor_id}, timestamp={self.timestamp}, value={self.value})>"


# Note: For InfluxDB integration, use this line protocol format:
# sensor_reading,sensor_id={sensor_id},asset_id={asset_id} value={value},value_x={value_x},value_y={value_y},value_z={value_z},value_rms={value_rms} {timestamp_ns}
