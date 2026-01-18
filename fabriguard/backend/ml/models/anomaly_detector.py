"""
Anomaly Detection Models for Predictive Maintenance

Implements multiple approaches for detecting equipment anomalies:
- Isolation Forest (unsupervised, good for high-dimensional data)
- Statistical methods (z-score, moving average deviation)
- Autoencoder-based (for complex patterns)
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import numpy as np
import pandas as pd
from dataclasses import dataclass
import joblib
import json

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from scipy import stats


@dataclass
class AnomalyResult:
    """Result of anomaly detection analysis."""
    is_anomaly: bool
    anomaly_score: float  # 0-1, higher = more anomalous
    confidence: float  # 0-1
    contributing_features: Dict[str, float]  # Feature contributions
    threshold_used: float
    model_version: str
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_anomaly": self.is_anomaly,
            "anomaly_score": self.anomaly_score,
            "confidence": self.confidence,
            "contributing_features": self.contributing_features,
            "threshold_used": self.threshold_used,
            "model_version": self.model_version,
            "timestamp": self.timestamp.isoformat()
        }


class AnomalyDetector(ABC):
    """Abstract base class for anomaly detectors."""

    def __init__(self, model_version: str = "1.0.0"):
        self.model_version = model_version
        self.is_fitted = False
        self.scaler: Optional[StandardScaler] = None
        self.feature_names: List[str] = []
        self.threshold = 0.5

    @abstractmethod
    def fit(self, data: pd.DataFrame) -> "AnomalyDetector":
        """Train the anomaly detector on normal operating data."""
        pass

    @abstractmethod
    def predict(self, data: pd.DataFrame) -> List[AnomalyResult]:
        """Detect anomalies in new data."""
        pass

    @abstractmethod
    def predict_single(self, features: Dict[str, float]) -> AnomalyResult:
        """Detect anomaly for a single data point."""
        pass

    def save(self, path: str) -> None:
        """Save model to disk."""
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str) -> "AnomalyDetector":
        """Load model from disk."""
        return joblib.load(path)

    def set_threshold(self, threshold: float) -> None:
        """Set the anomaly detection threshold."""
        self.threshold = max(0.0, min(1.0, threshold))


class IsolationForestDetector(AnomalyDetector):
    """
    Isolation Forest based anomaly detector.

    Good for:
    - High-dimensional sensor data
    - Detecting point anomalies
    - No need for labeled anomaly data

    The algorithm isolates anomalies by randomly selecting features
    and split values, with anomalies requiring fewer splits to isolate.
    """

    def __init__(
        self,
        model_version: str = "1.0.0",
        contamination: float = 0.05,
        n_estimators: int = 100,
        max_samples: str = "auto",
        random_state: int = 42
    ):
        super().__init__(model_version)
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.random_state = random_state

        self.model: Optional[IsolationForest] = None
        self.baseline_scores: Optional[np.ndarray] = None

    def fit(self, data: pd.DataFrame) -> "IsolationForestDetector":
        """
        Train on normal operating data.

        Args:
            data: DataFrame with sensor features (should be "normal" data)

        Returns:
            Self for method chaining
        """
        self.feature_names = list(data.columns)

        # Scale features
        self.scaler = StandardScaler()
        scaled_data = self.scaler.fit_transform(data)

        # Train Isolation Forest
        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            max_samples=self.max_samples,
            random_state=self.random_state,
            n_jobs=-1
        )
        self.model.fit(scaled_data)

        # Calculate baseline scores for calibration
        self.baseline_scores = self.model.decision_function(scaled_data)

        self.is_fitted = True
        return self

    def predict(self, data: pd.DataFrame) -> List[AnomalyResult]:
        """
        Detect anomalies in batch.

        Args:
            data: DataFrame with same features as training

        Returns:
            List of AnomalyResult for each row
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        # Ensure feature alignment
        data = data[self.feature_names]

        # Scale
        scaled_data = self.scaler.transform(data)

        # Get raw scores (negative = anomaly in sklearn)
        raw_scores = self.model.decision_function(scaled_data)

        # Convert to 0-1 anomaly scores (higher = more anomalous)
        anomaly_scores = self._normalize_scores(raw_scores)

        # Get predictions
        predictions = self.model.predict(scaled_data)  # -1 = anomaly, 1 = normal

        results = []
        now = datetime.utcnow()

        for i in range(len(data)):
            # Calculate feature contributions using SHAP-like approach
            contributions = self._calculate_contributions(scaled_data[i])

            result = AnomalyResult(
                is_anomaly=predictions[i] == -1 or anomaly_scores[i] > self.threshold,
                anomaly_score=float(anomaly_scores[i]),
                confidence=self._calculate_confidence(anomaly_scores[i]),
                contributing_features=contributions,
                threshold_used=self.threshold,
                model_version=self.model_version,
                timestamp=now
            )
            results.append(result)

        return results

    def predict_single(self, features: Dict[str, float]) -> AnomalyResult:
        """Detect anomaly for single data point."""
        df = pd.DataFrame([features])
        return self.predict(df)[0]

    def _normalize_scores(self, raw_scores: np.ndarray) -> np.ndarray:
        """
        Normalize Isolation Forest scores to 0-1 range.

        Raw scores are centered around 0, with negative = more anomalous.
        """
        if self.baseline_scores is None:
            # Simple normalization
            min_score = raw_scores.min()
            max_score = raw_scores.max()
            if max_score == min_score:
                return np.zeros_like(raw_scores)
            return 1 - (raw_scores - min_score) / (max_score - min_score)

        # Use baseline for better calibration
        # Score of 0 maps to threshold, negative maps higher
        baseline_std = np.std(self.baseline_scores)
        baseline_mean = np.mean(self.baseline_scores)

        # Z-score relative to baseline, then map to 0-1
        z_scores = (baseline_mean - raw_scores) / (baseline_std + 1e-10)

        # Sigmoid to map to 0-1
        anomaly_scores = 1 / (1 + np.exp(-z_scores))

        return anomaly_scores

    def _calculate_confidence(self, anomaly_score: float) -> float:
        """
        Calculate confidence in the prediction.

        Confidence is higher when score is far from threshold.
        """
        distance_from_threshold = abs(anomaly_score - self.threshold)
        # Scale to 0-1 with max confidence at extremes
        confidence = min(1.0, distance_from_threshold * 2 + 0.5)
        return confidence

    def _calculate_contributions(self, scaled_features: np.ndarray) -> Dict[str, float]:
        """
        Estimate feature contributions to anomaly score.

        Uses a simple perturbation-based approach.
        """
        contributions = {}
        base_score = self.model.decision_function([scaled_features])[0]

        for i, feature_name in enumerate(self.feature_names):
            # Create perturbed version (set to mean = 0 in scaled space)
            perturbed = scaled_features.copy()
            perturbed[i] = 0

            perturbed_score = self.model.decision_function([perturbed])[0]

            # Contribution is how much the score changes
            contribution = base_score - perturbed_score
            contributions[feature_name] = float(contribution)

        # Normalize contributions
        total = sum(abs(v) for v in contributions.values())
        if total > 0:
            contributions = {k: v / total for k, v in contributions.items()}

        return contributions


class StatisticalAnomalyDetector(AnomalyDetector):
    """
    Statistical methods for anomaly detection.

    Uses z-scores and moving average deviations for simple,
    interpretable anomaly detection.
    """

    def __init__(
        self,
        model_version: str = "1.0.0",
        z_threshold: float = 3.0,
        window_size: int = 100
    ):
        super().__init__(model_version)
        self.z_threshold = z_threshold
        self.window_size = window_size

        self.means: Dict[str, float] = {}
        self.stds: Dict[str, float] = {}

    def fit(self, data: pd.DataFrame) -> "StatisticalAnomalyDetector":
        """Calculate baseline statistics from normal data."""
        self.feature_names = list(data.columns)

        for col in data.columns:
            self.means[col] = float(data[col].mean())
            self.stds[col] = float(data[col].std())

        self.is_fitted = True
        return self

    def predict(self, data: pd.DataFrame) -> List[AnomalyResult]:
        """Detect anomalies using z-scores."""
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        results = []
        now = datetime.utcnow()

        for i, row in data.iterrows():
            z_scores = {}
            for col in self.feature_names:
                if self.stds[col] > 0:
                    z_scores[col] = (row[col] - self.means[col]) / self.stds[col]
                else:
                    z_scores[col] = 0

            # Max absolute z-score determines anomaly
            max_z = max(abs(z) for z in z_scores.values())
            anomaly_score = min(1.0, max_z / (self.z_threshold * 2))

            is_anomaly = max_z > self.z_threshold

            result = AnomalyResult(
                is_anomaly=is_anomaly,
                anomaly_score=anomaly_score,
                confidence=min(1.0, max_z / self.z_threshold) if is_anomaly else 0.8,
                contributing_features={k: abs(v) / (sum(abs(z) for z in z_scores.values()) + 1e-10)
                                      for k, v in z_scores.items()},
                threshold_used=self.threshold,
                model_version=self.model_version,
                timestamp=now
            )
            results.append(result)

        return results

    def predict_single(self, features: Dict[str, float]) -> AnomalyResult:
        """Detect anomaly for single data point."""
        df = pd.DataFrame([features])
        return self.predict(df)[0]


class EnsembleAnomalyDetector(AnomalyDetector):
    """
    Ensemble of multiple anomaly detectors.

    Combines predictions from multiple models for more robust detection.
    """

    def __init__(
        self,
        model_version: str = "1.0.0",
        detectors: Optional[List[AnomalyDetector]] = None,
        weights: Optional[List[float]] = None
    ):
        super().__init__(model_version)

        if detectors is None:
            # Default ensemble
            self.detectors = [
                IsolationForestDetector(contamination=0.05),
                StatisticalAnomalyDetector(z_threshold=3.0)
            ]
        else:
            self.detectors = detectors

        if weights is None:
            self.weights = [1.0 / len(self.detectors)] * len(self.detectors)
        else:
            total = sum(weights)
            self.weights = [w / total for w in weights]

    def fit(self, data: pd.DataFrame) -> "EnsembleAnomalyDetector":
        """Train all detectors."""
        self.feature_names = list(data.columns)

        for detector in self.detectors:
            detector.fit(data)

        self.is_fitted = True
        return self

    def predict(self, data: pd.DataFrame) -> List[AnomalyResult]:
        """Combine predictions from all detectors."""
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        # Get predictions from all detectors
        all_results = [d.predict(data) for d in self.detectors]

        combined_results = []
        now = datetime.utcnow()

        for i in range(len(data)):
            # Weighted average of anomaly scores
            weighted_score = sum(
                w * results[i].anomaly_score
                for w, results in zip(self.weights, all_results)
            )

            # Majority vote for is_anomaly
            anomaly_votes = sum(
                1 for results in all_results if results[i].is_anomaly
            )
            is_anomaly = anomaly_votes > len(self.detectors) / 2

            # Combine contributions
            all_contributions = [results[i].contributing_features for results in all_results]
            combined_contributions = {}
            for contrib in all_contributions:
                for k, v in contrib.items():
                    combined_contributions[k] = combined_contributions.get(k, 0) + v
            total = sum(combined_contributions.values())
            if total > 0:
                combined_contributions = {k: v / total for k, v in combined_contributions.items()}

            result = AnomalyResult(
                is_anomaly=is_anomaly or weighted_score > self.threshold,
                anomaly_score=weighted_score,
                confidence=sum(w * r[i].confidence for w, r in zip(self.weights, all_results)),
                contributing_features=combined_contributions,
                threshold_used=self.threshold,
                model_version=self.model_version,
                timestamp=now
            )
            combined_results.append(result)

        return combined_results

    def predict_single(self, features: Dict[str, float]) -> AnomalyResult:
        """Detect anomaly for single data point."""
        df = pd.DataFrame([features])
        return self.predict(df)[0]
