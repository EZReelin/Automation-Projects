"""
ML Inference Engine

Coordinates feature extraction and model inference for real-time
predictive maintenance predictions.
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import pandas as pd
import numpy as np
from pathlib import Path
import json
from dataclasses import dataclass, asdict
import structlog

from ml.models.anomaly_detector import AnomalyDetector, IsolationForestDetector, EnsembleAnomalyDetector
from ml.models.rul_predictor import RULPredictor, GradientBoostingRUL, EnsembleRULPredictor
from ml.models.health_scorer import HealthScorer, EquipmentSpecificHealthScorer
from ml.models.failure_classifier import FailureClassifier, RuleBasedFailureClassifier
from ml.features.extractor import FeatureExtractor, EquipmentFeatureExtractor

logger = structlog.get_logger(__name__)


@dataclass
class InferenceResult:
    """Complete inference result for an asset."""
    asset_id: str
    timestamp: datetime
    health_score: float
    status: str  # healthy, warning, critical
    anomaly_detected: bool
    anomaly_score: float
    rul_days: Optional[int]
    rul_confidence: float
    predicted_failure_mode: Optional[str]
    failure_confidence: float
    recommendations: List[str]
    contributing_factors: Dict[str, float]
    should_alert: bool
    alert_severity: Optional[str]
    model_versions: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class InferenceEngine:
    """
    Coordinates ML model inference for predictive maintenance.

    Manages:
    - Model loading and caching
    - Feature extraction
    - Multi-model inference pipeline
    - Result aggregation and alerting decisions
    """

    def __init__(
        self,
        model_path: str = "./models",
        anomaly_threshold: float = 0.7,
        rul_warning_days: int = 30,
        rul_critical_days: int = 7
    ):
        self.model_path = Path(model_path)
        self.anomaly_threshold = anomaly_threshold
        self.rul_warning_days = rul_warning_days
        self.rul_critical_days = rul_critical_days

        # Models (lazy loaded)
        self._anomaly_detector: Optional[AnomalyDetector] = None
        self._rul_predictor: Optional[RULPredictor] = None
        self._failure_classifier: Optional[FailureClassifier] = None
        self._health_scorer: Optional[HealthScorer] = None

        # Equipment-specific components
        self.equipment_feature_extractor = EquipmentFeatureExtractor()
        self.equipment_health_scorer = EquipmentSpecificHealthScorer()

        # Model versions
        self.model_versions = {
            "anomaly": "1.0.0",
            "rul": "1.0.0",
            "failure": "1.0.0",
            "health": "1.0.0"
        }

        # Inference statistics
        self.inference_count = 0
        self.alerts_generated = 0

    @property
    def anomaly_detector(self) -> AnomalyDetector:
        """Lazy load anomaly detector."""
        if self._anomaly_detector is None:
            model_file = self.model_path / "anomaly_detector.joblib"
            if model_file.exists():
                self._anomaly_detector = AnomalyDetector.load(str(model_file))
            else:
                # Use default ensemble detector
                self._anomaly_detector = EnsembleAnomalyDetector()
                logger.info("Using default anomaly detector (not trained)")
        return self._anomaly_detector

    @property
    def rul_predictor(self) -> RULPredictor:
        """Lazy load RUL predictor."""
        if self._rul_predictor is None:
            model_file = self.model_path / "rul_predictor.joblib"
            if model_file.exists():
                self._rul_predictor = RULPredictor.load(str(model_file))
            else:
                self._rul_predictor = EnsembleRULPredictor()
                logger.info("Using default RUL predictor (not trained)")
        return self._rul_predictor

    @property
    def failure_classifier(self) -> FailureClassifier:
        """Lazy load failure classifier."""
        if self._failure_classifier is None:
            model_file = self.model_path / "failure_classifier.joblib"
            if model_file.exists():
                self._failure_classifier = FailureClassifier.load(str(model_file))
            else:
                # Use rule-based classifier for initial deployment
                self._failure_classifier = RuleBasedFailureClassifier()
                logger.info("Using rule-based failure classifier")
        return self._failure_classifier

    @property
    def health_scorer(self) -> HealthScorer:
        """Lazy load health scorer."""
        if self._health_scorer is None:
            self._health_scorer = HealthScorer()
        return self._health_scorer

    def run_inference(
        self,
        asset_id: str,
        sensor_data: pd.DataFrame,
        equipment_type: str = "default",
        operating_hours: float = 0,
        days_since_maintenance: int = 0,
        maintenance_interval_days: int = 90
    ) -> InferenceResult:
        """
        Run complete inference pipeline for an asset.

        Args:
            asset_id: Unique identifier for the asset
            sensor_data: DataFrame with sensor readings
            equipment_type: Type of equipment for specialized models
            operating_hours: Total operating hours
            days_since_maintenance: Days since last maintenance
            maintenance_interval_days: Scheduled maintenance interval

        Returns:
            InferenceResult with all predictions and recommendations
        """
        now = datetime.utcnow()
        self.inference_count += 1

        logger.info(
            "Running inference",
            asset_id=asset_id,
            equipment_type=equipment_type,
            sensor_count=len(sensor_data.columns)
        )

        # 1. Extract features
        feature_extractor = self.equipment_feature_extractor.get_extractor(equipment_type)
        extracted = feature_extractor.extract_all(sensor_data)
        features = extracted.features

        if not features:
            logger.warning("No features extracted", asset_id=asset_id)
            return self._create_default_result(asset_id, now)

        # Convert to DataFrame for model input
        feature_df = pd.DataFrame([features])

        # 2. Anomaly Detection
        try:
            if self.anomaly_detector.is_fitted:
                anomaly_result = self.anomaly_detector.predict_single(features)
                anomaly_detected = anomaly_result.is_anomaly
                anomaly_score = anomaly_result.anomaly_score
                anomaly_contributions = anomaly_result.contributing_features
            else:
                anomaly_detected = False
                anomaly_score = 0.0
                anomaly_contributions = {}
        except Exception as e:
            logger.error("Anomaly detection failed", error=str(e))
            anomaly_detected = False
            anomaly_score = 0.0
            anomaly_contributions = {}

        # 3. RUL Prediction
        try:
            if self.rul_predictor.is_fitted:
                rul_result = self.rul_predictor.predict_single(features)
                rul_days = rul_result.rul_days
                rul_confidence = rul_result.confidence_score
                rul_contributions = rul_result.contributing_features
            else:
                rul_days = None
                rul_confidence = 0.0
                rul_contributions = {}
        except Exception as e:
            logger.error("RUL prediction failed", error=str(e))
            rul_days = None
            rul_confidence = 0.0
            rul_contributions = {}

        # 4. Failure Classification (if anomaly detected)
        predicted_failure_mode = None
        failure_confidence = 0.0
        failure_actions = []

        if anomaly_detected and anomaly_score > 0.5:
            try:
                failure_result = self.failure_classifier.predict_single(features)
                predicted_failure_mode = failure_result.predicted_mode.value
                failure_confidence = failure_result.confidence
                failure_actions = failure_result.recommended_actions
            except Exception as e:
                logger.error("Failure classification failed", error=str(e))

        # 5. Health Score Calculation
        health_scorer = self.equipment_health_scorer.get_scorer(equipment_type)
        health_result = health_scorer.calculate(
            sensor_readings=self._get_latest_readings(sensor_data),
            anomaly_score=anomaly_score,
            rul_days=rul_days,
            operating_hours=operating_hours,
            maintenance_interval_days=maintenance_interval_days,
            days_since_maintenance=days_since_maintenance
        )

        health_score = health_result.score
        status = health_result.status
        recommendations = health_result.recommendations + failure_actions

        # 6. Aggregate contributing factors
        contributing_factors = {}
        for source, contrib in [
            ("anomaly", anomaly_contributions),
            ("rul", rul_contributions)
        ]:
            for k, v in contrib.items():
                key = f"{source}_{k}"
                contributing_factors[key] = v

        # 7. Determine if alert should be generated
        should_alert, alert_severity = self._determine_alert(
            anomaly_detected=anomaly_detected,
            anomaly_score=anomaly_score,
            rul_days=rul_days,
            health_score=health_score
        )

        if should_alert:
            self.alerts_generated += 1

        result = InferenceResult(
            asset_id=asset_id,
            timestamp=now,
            health_score=health_score,
            status=status,
            anomaly_detected=anomaly_detected,
            anomaly_score=anomaly_score,
            rul_days=rul_days,
            rul_confidence=rul_confidence,
            predicted_failure_mode=predicted_failure_mode,
            failure_confidence=failure_confidence,
            recommendations=recommendations[:5],  # Top 5 recommendations
            contributing_factors=contributing_factors,
            should_alert=should_alert,
            alert_severity=alert_severity,
            model_versions=self.model_versions
        )

        logger.info(
            "Inference complete",
            asset_id=asset_id,
            health_score=health_score,
            status=status,
            anomaly_detected=anomaly_detected,
            should_alert=should_alert
        )

        return result

    def _determine_alert(
        self,
        anomaly_detected: bool,
        anomaly_score: float,
        rul_days: Optional[int],
        health_score: float
    ) -> Tuple[bool, Optional[str]]:
        """Determine if an alert should be generated and its severity."""

        # Emergency conditions
        if rul_days is not None and rul_days <= self.rul_critical_days:
            return True, "emergency"

        if anomaly_score > 0.9:
            return True, "critical"

        # Critical conditions
        if health_score < 30:
            return True, "critical"

        if anomaly_detected and anomaly_score > self.anomaly_threshold:
            return True, "warning"

        # Warning conditions
        if rul_days is not None and rul_days <= self.rul_warning_days:
            return True, "warning"

        if health_score < 50:
            return True, "warning"

        # Info conditions
        if anomaly_detected:
            return True, "info"

        return False, None

    def _get_latest_readings(self, sensor_data: pd.DataFrame) -> Dict[str, float]:
        """Get the most recent reading for each sensor."""
        return {col: float(sensor_data[col].iloc[-1]) for col in sensor_data.columns}

    def _create_default_result(self, asset_id: str, timestamp: datetime) -> InferenceResult:
        """Create a default result when inference cannot be performed."""
        return InferenceResult(
            asset_id=asset_id,
            timestamp=timestamp,
            health_score=100.0,
            status="unknown",
            anomaly_detected=False,
            anomaly_score=0.0,
            rul_days=None,
            rul_confidence=0.0,
            predicted_failure_mode=None,
            failure_confidence=0.0,
            recommendations=["Insufficient data for analysis"],
            contributing_factors={},
            should_alert=False,
            alert_severity=None,
            model_versions=self.model_versions
        )

    def batch_inference(
        self,
        assets: List[Dict[str, Any]]
    ) -> List[InferenceResult]:
        """
        Run inference for multiple assets.

        Args:
            assets: List of dicts with asset_id, sensor_data, equipment_type, etc.

        Returns:
            List of InferenceResults
        """
        results = []
        for asset in assets:
            try:
                result = self.run_inference(
                    asset_id=asset["asset_id"],
                    sensor_data=asset["sensor_data"],
                    equipment_type=asset.get("equipment_type", "default"),
                    operating_hours=asset.get("operating_hours", 0),
                    days_since_maintenance=asset.get("days_since_maintenance", 0),
                    maintenance_interval_days=asset.get("maintenance_interval_days", 90)
                )
                results.append(result)
            except Exception as e:
                logger.error(
                    "Batch inference failed for asset",
                    asset_id=asset.get("asset_id"),
                    error=str(e)
                )
                results.append(
                    self._create_default_result(
                        asset.get("asset_id", "unknown"),
                        datetime.utcnow()
                    )
                )

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get inference engine statistics."""
        return {
            "inference_count": self.inference_count,
            "alerts_generated": self.alerts_generated,
            "alert_rate": self.alerts_generated / max(1, self.inference_count),
            "model_versions": self.model_versions,
            "models_loaded": {
                "anomaly": self._anomaly_detector is not None,
                "rul": self._rul_predictor is not None,
                "failure": self._failure_classifier is not None,
                "health": self._health_scorer is not None
            }
        }

    def reload_models(self) -> None:
        """Force reload all models from disk."""
        self._anomaly_detector = None
        self._rul_predictor = None
        self._failure_classifier = None
        self._health_scorer = None
        logger.info("Models cleared for reload")
