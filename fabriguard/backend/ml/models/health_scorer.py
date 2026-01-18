"""
Health Score Calculator

Computes overall equipment health scores from multiple indicators,
providing a single 0-100 score for dashboard display.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import numpy as np
import pandas as pd
from dataclasses import dataclass


@dataclass
class HealthScore:
    """Result of health score calculation."""
    score: float  # 0-100
    status: str  # "healthy", "warning", "critical"
    component_scores: Dict[str, float]  # Individual component scores
    degradation_rate: float  # Score change per day
    trend: str  # "improving", "stable", "degrading"
    contributing_factors: Dict[str, float]
    recommendations: List[str]
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "status": self.status,
            "component_scores": self.component_scores,
            "degradation_rate": self.degradation_rate,
            "trend": self.trend,
            "contributing_factors": self.contributing_factors,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp.isoformat()
        }


class HealthScorer:
    """
    Calculates equipment health scores.

    Combines multiple indicators into a single health score:
    - Anomaly scores from detection models
    - RUL predictions
    - Sensor deviation from baselines
    - Operating condition assessments
    """

    def __init__(
        self,
        model_version: str = "1.0.0",
        weights: Optional[Dict[str, float]] = None
    ):
        self.model_version = model_version

        # Default weights for combining different health indicators
        self.weights = weights or {
            "anomaly": 0.3,
            "rul": 0.3,
            "sensor_deviation": 0.25,
            "operating_conditions": 0.15
        }

        # Thresholds for status determination
        self.thresholds = {
            "healthy": 80,
            "warning": 50,
            "critical": 0
        }

        # Component baselines (learned from data)
        self.baselines: Dict[str, Dict[str, float]] = {}
        self.historical_scores: List[float] = []

    def calculate(
        self,
        sensor_readings: Dict[str, float],
        anomaly_score: Optional[float] = None,
        rul_days: Optional[int] = None,
        operating_hours: float = 0,
        maintenance_interval_days: int = 90,
        days_since_maintenance: int = 0
    ) -> HealthScore:
        """
        Calculate comprehensive health score.

        Args:
            sensor_readings: Current sensor values
            anomaly_score: Score from anomaly detector (0-1)
            rul_days: Remaining useful life prediction
            operating_hours: Total operating hours
            maintenance_interval_days: Scheduled maintenance interval
            days_since_maintenance: Days since last maintenance
        """
        component_scores = {}
        contributions = {}
        recommendations = []
        now = datetime.utcnow()

        # 1. Anomaly-based score (inverted - low anomaly = high health)
        if anomaly_score is not None:
            anomaly_health = max(0, 100 * (1 - anomaly_score))
            component_scores["anomaly"] = anomaly_health
            contributions["anomaly_detection"] = anomaly_score

            if anomaly_score > 0.7:
                recommendations.append(
                    "High anomaly score detected. Schedule immediate inspection."
                )
            elif anomaly_score > 0.5:
                recommendations.append(
                    "Elevated anomaly levels. Monitor closely and plan inspection."
                )

        # 2. RUL-based score
        if rul_days is not None:
            if rul_days <= 0:
                rul_health = 0
            elif rul_days <= 7:
                rul_health = 20
            elif rul_days <= 30:
                rul_health = 40 + (rul_days - 7) * 2
            elif rul_days <= 90:
                rul_health = 70 + (rul_days - 30) * 0.5
            else:
                rul_health = min(100, 85 + (rul_days - 90) * 0.1)

            component_scores["rul"] = rul_health
            contributions["predicted_life"] = 1 - (rul_health / 100)

            if rul_days <= 7:
                recommendations.append(
                    f"Critical: Only {rul_days} days of useful life remaining. "
                    "Schedule maintenance immediately."
                )
            elif rul_days <= 30:
                recommendations.append(
                    f"Warning: {rul_days} days until predicted maintenance needed. "
                    "Begin planning maintenance activities."
                )

        # 3. Sensor deviation score
        if sensor_readings and self.baselines:
            deviations = []
            for sensor_name, value in sensor_readings.items():
                if sensor_name in self.baselines:
                    baseline = self.baselines[sensor_name]
                    mean = baseline.get("mean", value)
                    std = baseline.get("std", 1)

                    if std > 0:
                        z_score = abs(value - mean) / std
                        deviation = min(1.0, z_score / 3)  # Cap at 3 sigma
                        deviations.append(deviation)
                        contributions[f"sensor_{sensor_name}"] = deviation

            if deviations:
                avg_deviation = np.mean(deviations)
                sensor_health = 100 * (1 - avg_deviation)
                component_scores["sensor_deviation"] = sensor_health

                if avg_deviation > 0.5:
                    recommendations.append(
                        "Multiple sensors showing significant deviation from baseline. "
                        "Review sensor data trends."
                    )

        # 4. Operating conditions score
        # Based on maintenance schedule adherence
        maintenance_due_ratio = days_since_maintenance / maintenance_interval_days

        if maintenance_due_ratio < 0.5:
            operating_health = 100
        elif maintenance_due_ratio < 0.8:
            operating_health = 100 - (maintenance_due_ratio - 0.5) * 50
        elif maintenance_due_ratio < 1.0:
            operating_health = 85 - (maintenance_due_ratio - 0.8) * 100
        else:
            # Overdue
            operating_health = max(30, 65 - (maintenance_due_ratio - 1.0) * 50)
            recommendations.append(
                f"Maintenance is overdue by {days_since_maintenance - maintenance_interval_days} days. "
                "Schedule maintenance as soon as possible."
            )

        component_scores["operating_conditions"] = operating_health
        contributions["maintenance_schedule"] = maintenance_due_ratio

        # Calculate weighted overall score
        total_weight = 0
        weighted_sum = 0

        for component, weight in self.weights.items():
            if component in component_scores:
                weighted_sum += weight * component_scores[component]
                total_weight += weight

        if total_weight > 0:
            overall_score = weighted_sum / total_weight
        else:
            overall_score = 100  # Default to healthy if no data

        # Determine status
        if overall_score >= self.thresholds["healthy"]:
            status = "healthy"
        elif overall_score >= self.thresholds["warning"]:
            status = "warning"
        else:
            status = "critical"

        # Calculate trend
        self.historical_scores.append(overall_score)
        if len(self.historical_scores) > 100:
            self.historical_scores = self.historical_scores[-100:]

        degradation_rate, trend = self._calculate_trend()

        # Normalize contributions
        total_contrib = sum(contributions.values())
        if total_contrib > 0:
            contributions = {k: v / total_contrib for k, v in contributions.items()}

        return HealthScore(
            score=round(overall_score, 1),
            status=status,
            component_scores=component_scores,
            degradation_rate=degradation_rate,
            trend=trend,
            contributing_factors=contributions,
            recommendations=recommendations,
            timestamp=now
        )

    def set_baselines(self, sensor_stats: Dict[str, Dict[str, float]]) -> None:
        """
        Set baseline statistics for sensors.

        Args:
            sensor_stats: Dict of sensor_name -> {"mean": float, "std": float}
        """
        self.baselines = sensor_stats

    def learn_baselines(self, data: pd.DataFrame) -> None:
        """
        Learn baselines from historical data.

        Args:
            data: DataFrame with sensor readings (normal operating data)
        """
        self.baselines = {}
        for col in data.columns:
            self.baselines[col] = {
                "mean": float(data[col].mean()),
                "std": float(data[col].std()),
                "min": float(data[col].min()),
                "max": float(data[col].max()),
                "p5": float(data[col].quantile(0.05)),
                "p95": float(data[col].quantile(0.95))
            }

    def _calculate_trend(self) -> tuple:
        """Calculate degradation rate and trend direction."""
        if len(self.historical_scores) < 5:
            return 0.0, "stable"

        recent = self.historical_scores[-10:]
        older = self.historical_scores[-20:-10] if len(self.historical_scores) >= 20 else self.historical_scores[:10]

        recent_avg = np.mean(recent)
        older_avg = np.mean(older)

        # Rate of change (points per day, assuming daily updates)
        degradation_rate = (older_avg - recent_avg) / len(recent)

        if degradation_rate > 2:
            trend = "degrading"
        elif degradation_rate < -2:
            trend = "improving"
        else:
            trend = "stable"

        return round(degradation_rate, 2), trend


class EquipmentSpecificHealthScorer:
    """
    Equipment-type specific health scoring.

    Provides specialized scoring logic for different equipment types.
    """

    def __init__(self):
        self.scorers: Dict[str, HealthScorer] = {}
        self._initialize_default_scorers()

    def _initialize_default_scorers(self):
        """Create scorers for each supported equipment type."""

        # CNC Machines - focus on spindle and axis health
        self.scorers["cnc_machining_center"] = HealthScorer(
            weights={
                "anomaly": 0.25,
                "rul": 0.35,
                "sensor_deviation": 0.30,
                "operating_conditions": 0.10
            }
        )

        # Hydraulic Press - focus on pump and seal health
        self.scorers["hydraulic_press"] = HealthScorer(
            weights={
                "anomaly": 0.30,
                "rul": 0.30,
                "sensor_deviation": 0.25,
                "operating_conditions": 0.15
            }
        )

        # Air Compressor - focus on motor and pressure
        self.scorers["air_compressor"] = HealthScorer(
            weights={
                "anomaly": 0.25,
                "rul": 0.25,
                "sensor_deviation": 0.35,
                "operating_conditions": 0.15
            }
        )

        # Default for other equipment
        self.scorers["default"] = HealthScorer()

    def get_scorer(self, equipment_type: str) -> HealthScorer:
        """Get appropriate scorer for equipment type."""
        return self.scorers.get(equipment_type, self.scorers["default"])

    def calculate(
        self,
        equipment_type: str,
        sensor_readings: Dict[str, float],
        **kwargs
    ) -> HealthScore:
        """Calculate health score using equipment-specific scorer."""
        scorer = self.get_scorer(equipment_type)
        return scorer.calculate(sensor_readings, **kwargs)
