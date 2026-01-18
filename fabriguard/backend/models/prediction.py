"""Prediction model for ML model outputs including RUL predictions."""
import uuid
from enum import Enum
from typing import TYPE_CHECKING, Optional
from datetime import datetime
from sqlalchemy import String, ForeignKey, Numeric, DateTime, Integer, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .asset import Asset


class PredictionType(str, Enum):
    """Types of ML predictions."""
    ANOMALY_DETECTION = "anomaly_detection"        # Deviation from normal
    RUL_PREDICTION = "rul_prediction"              # Remaining Useful Life
    FAILURE_CLASSIFICATION = "failure_classification"  # Type of failure
    HEALTH_SCORE = "health_score"                  # Overall health assessment
    TREND_ANALYSIS = "trend_analysis"              # Degradation trend


class Prediction(Base, TimestampMixin):
    """
    Prediction represents an ML model output for an asset.

    Predictions are generated periodically and stored for trend
    analysis, model improvement, and audit trail purposes.
    """
    __tablename__ = "predictions"

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

    # Prediction Metadata
    prediction_type: Mapped[PredictionType] = mapped_column(
        SQLEnum(PredictionType),
        nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    # Time Window
    prediction_window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    prediction_window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Primary Prediction Output
    prediction_value: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    prediction_unit: Mapped[str] = mapped_column(String(50))  # days, score, class

    # Confidence & Uncertainty
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)  # 0-1
    confidence_lower: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))  # Lower bound
    confidence_upper: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))  # Upper bound
    confidence_level: Mapped[float] = mapped_column(Numeric(5, 4), default=0.95)  # e.g., 95%

    # RUL Specific Fields
    rul_days: Mapped[Optional[int]] = mapped_column(Integer)
    rul_hours: Mapped[Optional[int]] = mapped_column(Integer)
    predicted_failure_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Anomaly Detection Specific
    anomaly_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))  # 0-1
    is_anomaly: Mapped[Optional[bool]] = mapped_column()
    anomaly_threshold: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))

    # Failure Classification Specific
    predicted_failure_mode: Mapped[Optional[str]] = mapped_column(String(100))
    failure_mode_probabilities: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Health Score Specific
    health_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))  # 0-100
    health_trend: Mapped[Optional[str]] = mapped_column(String(20))  # improving, stable, degrading

    # Feature Importance (explainability)
    top_features: Mapped[Optional[dict]] = mapped_column(JSONB)
    feature_values: Mapped[Optional[dict]] = mapped_column(JSONB)
    shap_values: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Input Data Summary
    input_sensor_count: Mapped[int] = mapped_column(Integer, default=0)
    input_reading_count: Mapped[int] = mapped_column(Integer, default=0)
    data_quality_score: Mapped[float] = mapped_column(Numeric(5, 4), default=1.0)

    # Generated Alert (if any)
    generated_alert_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    alert_generated: Mapped[bool] = mapped_column(default=False)

    # Model Performance Tracking
    actual_outcome: Mapped[Optional[str]] = mapped_column(String(100))
    outcome_recorded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    was_accurate: Mapped[Optional[bool]] = mapped_column()
    error_magnitude: Mapped[Optional[float]] = mapped_column(Numeric(18, 8))

    # Debug/Audit Information
    processing_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    raw_model_output: Mapped[Optional[dict]] = mapped_column(JSONB)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    asset: Mapped["Asset"] = relationship(
        "Asset",
        back_populates="predictions"
    )

    @property
    def requires_attention(self) -> bool:
        """Check if prediction indicates need for attention."""
        if self.prediction_type == PredictionType.ANOMALY_DETECTION:
            return self.is_anomaly or False
        elif self.prediction_type == PredictionType.RUL_PREDICTION:
            return (self.rul_days or 999) < 30
        elif self.prediction_type == PredictionType.HEALTH_SCORE:
            return (self.health_score or 100) < 70
        return False

    def __repr__(self) -> str:
        return f"<Prediction(id={self.id}, type={self.prediction_type}, value={self.prediction_value}, confidence={self.confidence_score})>"
