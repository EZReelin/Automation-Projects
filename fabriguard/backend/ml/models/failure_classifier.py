"""
Failure Mode Classification

Classifies the type of failure based on sensor patterns,
providing actionable information for maintenance planning.
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import numpy as np
import pandas as pd
from dataclasses import dataclass
from enum import Enum
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder


class FailureModeType(str, Enum):
    """Standard failure modes for metal fabrication equipment."""
    # Mechanical
    BEARING_WEAR = "bearing_wear"
    BEARING_LUBRICATION = "bearing_lubrication"
    SHAFT_MISALIGNMENT = "shaft_misalignment"
    SHAFT_IMBALANCE = "shaft_imbalance"
    GEAR_WEAR = "gear_wear"
    BELT_WEAR = "belt_wear"

    # Hydraulic
    PUMP_DEGRADATION = "pump_degradation"
    SEAL_WEAR = "seal_wear"
    VALVE_FAILURE = "valve_failure"
    HYDRAULIC_LEAK = "hydraulic_leak"

    # Electrical
    MOTOR_OVERLOAD = "motor_overload"
    MOTOR_INSULATION = "motor_insulation"
    ELECTRICAL_FAULT = "electrical_fault"

    # Thermal
    OVERHEATING = "overheating"
    COOLING_FAILURE = "cooling_failure"

    # Other
    FILTER_CLOGGED = "filter_clogged"
    PRESSURE_ABNORMAL = "pressure_abnormal"
    UNKNOWN = "unknown"


@dataclass
class FailureClassification:
    """Result of failure classification."""
    predicted_mode: FailureModeType
    confidence: float
    probabilities: Dict[str, float]  # All class probabilities
    contributing_features: Dict[str, float]
    recommended_actions: List[str]
    urgency: str  # "immediate", "soon", "scheduled"
    model_version: str
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "predicted_mode": self.predicted_mode.value,
            "confidence": self.confidence,
            "probabilities": self.probabilities,
            "contributing_features": self.contributing_features,
            "recommended_actions": self.recommended_actions,
            "urgency": self.urgency,
            "model_version": self.model_version,
            "timestamp": self.timestamp.isoformat()
        }


class FailureClassifier:
    """
    Classifies failure modes from sensor data.

    Uses Random Forest for interpretable multi-class classification
    with probability outputs.
    """

    def __init__(
        self,
        model_version: str = "1.0.0",
        n_estimators: int = 100,
        max_depth: int = 10,
        random_state: int = 42
    ):
        self.model_version = model_version
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.random_state = random_state

        self.model: Optional[RandomForestClassifier] = None
        self.scaler: Optional[StandardScaler] = None
        self.label_encoder: Optional[LabelEncoder] = None
        self.feature_names: List[str] = []
        self.is_fitted = False

        # Recommended actions for each failure mode
        self.action_map = self._initialize_action_map()

    def _initialize_action_map(self) -> Dict[FailureModeType, Dict[str, Any]]:
        """Initialize recommended actions for each failure mode."""
        return {
            FailureModeType.BEARING_WEAR: {
                "actions": [
                    "Schedule bearing inspection",
                    "Check vibration levels and patterns",
                    "Prepare replacement bearings",
                    "Review lubrication schedule"
                ],
                "urgency_threshold": 0.7
            },
            FailureModeType.BEARING_LUBRICATION: {
                "actions": [
                    "Check lubricant levels immediately",
                    "Inspect for contamination",
                    "Re-lubricate bearing assemblies",
                    "Review lubrication schedule"
                ],
                "urgency_threshold": 0.8
            },
            FailureModeType.SHAFT_MISALIGNMENT: {
                "actions": [
                    "Perform alignment check",
                    "Inspect coupling condition",
                    "Check mounting bolts torque",
                    "Schedule laser alignment service"
                ],
                "urgency_threshold": 0.6
            },
            FailureModeType.SHAFT_IMBALANCE: {
                "actions": [
                    "Perform dynamic balancing",
                    "Inspect rotating components",
                    "Check for loose components",
                    "Review recent maintenance work"
                ],
                "urgency_threshold": 0.6
            },
            FailureModeType.PUMP_DEGRADATION: {
                "actions": [
                    "Check pump pressure output",
                    "Inspect pump seals and gaskets",
                    "Check hydraulic fluid condition",
                    "Schedule pump rebuild or replacement"
                ],
                "urgency_threshold": 0.7
            },
            FailureModeType.SEAL_WEAR: {
                "actions": [
                    "Inspect all visible seals for leaks",
                    "Check hydraulic fluid levels",
                    "Order replacement seal kits",
                    "Schedule seal replacement"
                ],
                "urgency_threshold": 0.75
            },
            FailureModeType.MOTOR_OVERLOAD: {
                "actions": [
                    "Check motor current draw immediately",
                    "Reduce load if possible",
                    "Inspect for mechanical binding",
                    "Verify cooling system operation"
                ],
                "urgency_threshold": 0.85
            },
            FailureModeType.OVERHEATING: {
                "actions": [
                    "Check cooling system immediately",
                    "Reduce operating load",
                    "Inspect ventilation and airflow",
                    "Check thermal protection devices"
                ],
                "urgency_threshold": 0.9
            },
            FailureModeType.FILTER_CLOGGED: {
                "actions": [
                    "Replace filters immediately",
                    "Check filter differential pressure",
                    "Inspect for contamination source",
                    "Review filter replacement schedule"
                ],
                "urgency_threshold": 0.65
            },
            FailureModeType.UNKNOWN: {
                "actions": [
                    "Perform comprehensive inspection",
                    "Review all sensor data trends",
                    "Consult equipment documentation",
                    "Contact technical support if needed"
                ],
                "urgency_threshold": 0.5
            }
        }

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "FailureClassifier":
        """
        Train the classifier on labeled failure data.

        Args:
            X: Feature DataFrame
            y: Failure mode labels
        """
        self.feature_names = list(X.columns)

        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        # Encode labels
        self.label_encoder = LabelEncoder()
        y_encoded = self.label_encoder.fit_transform(y)

        # Train classifier
        self.model = RandomForestClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            random_state=self.random_state,
            n_jobs=-1,
            class_weight='balanced'
        )
        self.model.fit(X_scaled, y_encoded)

        self.is_fitted = True
        return self

    def predict(self, X: pd.DataFrame) -> List[FailureClassification]:
        """Classify failure modes for multiple samples."""
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        X = X[self.feature_names]
        X_scaled = self.scaler.transform(X)

        # Get predictions and probabilities
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)

        # Get feature importances
        importances = self.model.feature_importances_
        feature_importance = {
            name: float(imp) for name, imp in zip(self.feature_names, importances)
        }

        results = []
        now = datetime.utcnow()

        for i in range(len(X)):
            pred_label = self.label_encoder.inverse_transform([predictions[i]])[0]

            try:
                failure_mode = FailureModeType(pred_label)
            except ValueError:
                failure_mode = FailureModeType.UNKNOWN

            # Get probability distribution
            prob_dict = {
                self.label_encoder.inverse_transform([j])[0]: float(probabilities[i][j])
                for j in range(len(self.label_encoder.classes_))
            }

            confidence = float(probabilities[i].max())

            # Get recommended actions
            mode_info = self.action_map.get(
                failure_mode,
                self.action_map[FailureModeType.UNKNOWN]
            )

            # Determine urgency
            if confidence >= mode_info["urgency_threshold"]:
                urgency = "immediate"
            elif confidence >= mode_info["urgency_threshold"] - 0.2:
                urgency = "soon"
            else:
                urgency = "scheduled"

            result = FailureClassification(
                predicted_mode=failure_mode,
                confidence=confidence,
                probabilities=prob_dict,
                contributing_features=feature_importance,
                recommended_actions=mode_info["actions"],
                urgency=urgency,
                model_version=self.model_version,
                timestamp=now
            )
            results.append(result)

        return results

    def predict_single(self, features: Dict[str, float]) -> FailureClassification:
        """Classify failure mode for single sample."""
        df = pd.DataFrame([features])
        return self.predict(df)[0]

    def save(self, path: str) -> None:
        """Save model to disk."""
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str) -> "FailureClassifier":
        """Load model from disk."""
        return joblib.load(path)


class RuleBasedFailureClassifier:
    """
    Rule-based failure classification for interpretable results.

    Uses domain knowledge to classify failures based on sensor patterns.
    Good for initial deployment before enough labeled data is available.
    """

    def __init__(self, model_version: str = "1.0.0"):
        self.model_version = model_version
        self.rules = self._initialize_rules()

    def _initialize_rules(self) -> List[Dict]:
        """Define classification rules based on domain knowledge."""
        return [
            # Bearing wear - high vibration RMS, specific frequencies
            {
                "mode": FailureModeType.BEARING_WEAR,
                "conditions": [
                    ("vibration_rms", ">", 0.5),
                    ("vibration_peak_freq", "in_range", (100, 1000))
                ],
                "confidence_base": 0.75
            },
            # Lubrication issues - increasing temperature, friction indicators
            {
                "mode": FailureModeType.BEARING_LUBRICATION,
                "conditions": [
                    ("temperature", ">", 70),
                    ("vibration_rms", ">", 0.3),
                    ("temperature_rate", ">", 0.5)
                ],
                "confidence_base": 0.70
            },
            # Shaft misalignment - 2x running speed vibration
            {
                "mode": FailureModeType.SHAFT_MISALIGNMENT,
                "conditions": [
                    ("vibration_2x", ">", 0.3),
                    ("axial_vibration", ">", 0.2)
                ],
                "confidence_base": 0.70
            },
            # Imbalance - 1x running speed dominant
            {
                "mode": FailureModeType.SHAFT_IMBALANCE,
                "conditions": [
                    ("vibration_1x", ">", 0.4),
                    ("radial_vibration", ">", 0.3)
                ],
                "confidence_base": 0.75
            },
            # Pump degradation - pressure drop, flow reduction
            {
                "mode": FailureModeType.PUMP_DEGRADATION,
                "conditions": [
                    ("pressure_drop", ">", 10),
                    ("flow_rate", "<", 0.8)  # relative to baseline
                ],
                "confidence_base": 0.70
            },
            # Motor overload - high current
            {
                "mode": FailureModeType.MOTOR_OVERLOAD,
                "conditions": [
                    ("current", ">", 1.1),  # 110% of rated
                    ("power_factor", "<", 0.8)
                ],
                "confidence_base": 0.80
            },
            # Overheating
            {
                "mode": FailureModeType.OVERHEATING,
                "conditions": [
                    ("temperature", ">", 85),
                ],
                "confidence_base": 0.85
            },
            # Filter clogged - pressure differential
            {
                "mode": FailureModeType.FILTER_CLOGGED,
                "conditions": [
                    ("filter_dp", ">", 15),  # psi
                ],
                "confidence_base": 0.80
            }
        ]

    def predict_single(self, features: Dict[str, float]) -> FailureClassification:
        """Classify failure using rules."""
        now = datetime.utcnow()

        matching_rules = []

        for rule in self.rules:
            matches = 0
            total_conditions = len(rule["conditions"])

            for feature, op, threshold in rule["conditions"]:
                if feature not in features:
                    continue

                value = features[feature]

                if op == ">" and value > threshold:
                    matches += 1
                elif op == "<" and value < threshold:
                    matches += 1
                elif op == "in_range" and threshold[0] <= value <= threshold[1]:
                    matches += 1

            if matches > 0:
                match_ratio = matches / total_conditions
                confidence = rule["confidence_base"] * match_ratio
                matching_rules.append((rule["mode"], confidence, rule))

        if not matching_rules:
            return FailureClassification(
                predicted_mode=FailureModeType.UNKNOWN,
                confidence=0.5,
                probabilities={FailureModeType.UNKNOWN.value: 1.0},
                contributing_features={},
                recommended_actions=["Perform comprehensive inspection"],
                urgency="scheduled",
                model_version=self.model_version,
                timestamp=now
            )

        # Sort by confidence
        matching_rules.sort(key=lambda x: x[1], reverse=True)
        best_mode, best_confidence, best_rule = matching_rules[0]

        # Build probability distribution
        total_conf = sum(conf for _, conf, _ in matching_rules)
        probabilities = {
            mode.value: conf / total_conf
            for mode, conf, _ in matching_rules
        }

        # Get actions from main classifier's action map
        action_map = FailureClassifier()._initialize_action_map()
        mode_info = action_map.get(best_mode, action_map[FailureModeType.UNKNOWN])

        if best_confidence >= mode_info["urgency_threshold"]:
            urgency = "immediate"
        elif best_confidence >= mode_info["urgency_threshold"] - 0.2:
            urgency = "soon"
        else:
            urgency = "scheduled"

        # Contributing features from matching conditions
        contributing = {}
        for feature, op, threshold in best_rule["conditions"]:
            if feature in features:
                contributing[feature] = 1.0 / len(best_rule["conditions"])

        return FailureClassification(
            predicted_mode=best_mode,
            confidence=best_confidence,
            probabilities=probabilities,
            contributing_features=contributing,
            recommended_actions=mode_info["actions"],
            urgency=urgency,
            model_version=self.model_version,
            timestamp=now
        )
