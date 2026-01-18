"""
Remaining Useful Life (RUL) Prediction Models

Predicts the time until equipment failure based on sensor data
and historical patterns. Provides confidence intervals for predictions.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from dataclasses import dataclass
import joblib

from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score


@dataclass
class RULPrediction:
    """Result of RUL prediction."""
    rul_days: int
    rul_hours: int
    predicted_failure_date: datetime
    confidence_score: float  # 0-1
    confidence_interval_lower: int  # days
    confidence_interval_upper: int  # days
    health_trend: str  # "improving", "stable", "degrading", "critical"
    contributing_features: Dict[str, float]
    model_version: str
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rul_days": self.rul_days,
            "rul_hours": self.rul_hours,
            "predicted_failure_date": self.predicted_failure_date.isoformat(),
            "confidence_score": self.confidence_score,
            "confidence_interval": {
                "lower": self.confidence_interval_lower,
                "upper": self.confidence_interval_upper
            },
            "health_trend": self.health_trend,
            "contributing_features": self.contributing_features,
            "model_version": self.model_version,
            "timestamp": self.timestamp.isoformat()
        }


class RULPredictor(ABC):
    """Abstract base class for RUL predictors."""

    def __init__(self, model_version: str = "1.0.0"):
        self.model_version = model_version
        self.is_fitted = False
        self.scaler: Optional[StandardScaler] = None
        self.feature_names: List[str] = []
        self.min_rul = 0
        self.max_rul = 365  # Maximum prediction horizon in days

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "RULPredictor":
        """
        Train the RUL predictor.

        Args:
            X: Feature DataFrame
            y: Target RUL values (in days)
        """
        pass

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> List[RULPrediction]:
        """Predict RUL for multiple samples."""
        pass

    @abstractmethod
    def predict_single(self, features: Dict[str, float]) -> RULPrediction:
        """Predict RUL for a single sample."""
        pass

    def save(self, path: str) -> None:
        """Save model to disk."""
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str) -> "RULPredictor":
        """Load model from disk."""
        return joblib.load(path)


class GradientBoostingRUL(RULPredictor):
    """
    Gradient Boosting based RUL predictor.

    Good for:
    - Tabular sensor data
    - Capturing non-linear degradation patterns
    - Feature importance interpretation

    Uses quantile regression for confidence intervals.
    """

    def __init__(
        self,
        model_version: str = "1.0.0",
        n_estimators: int = 100,
        max_depth: int = 5,
        learning_rate: float = 0.1,
        random_state: int = 42
    ):
        super().__init__(model_version)
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.random_state = random_state

        # Main model for point prediction
        self.model: Optional[GradientBoostingRegressor] = None
        # Models for confidence intervals
        self.model_lower: Optional[GradientBoostingRegressor] = None
        self.model_upper: Optional[GradientBoostingRegressor] = None

        self.feature_importances_: Dict[str, float] = {}

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "GradientBoostingRUL":
        """
        Train on historical data with known RUL values.

        Args:
            X: Feature DataFrame (sensor readings, operating hours, etc.)
            y: Actual RUL in days at time of reading
        """
        self.feature_names = list(X.columns)

        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        # Train main model (median/mean prediction)
        self.model = GradientBoostingRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            loss='squared_error',
            random_state=self.random_state
        )
        self.model.fit(X_scaled, y)

        # Train quantile models for confidence intervals
        self.model_lower = GradientBoostingRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            loss='quantile',
            alpha=0.1,  # 10th percentile
            random_state=self.random_state
        )
        self.model_lower.fit(X_scaled, y)

        self.model_upper = GradientBoostingRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            loss='quantile',
            alpha=0.9,  # 90th percentile
            random_state=self.random_state
        )
        self.model_upper.fit(X_scaled, y)

        # Store feature importances
        importances = self.model.feature_importances_
        self.feature_importances_ = {
            name: float(imp) for name, imp in zip(self.feature_names, importances)
        }

        self.is_fitted = True
        return self

    def predict(self, X: pd.DataFrame) -> List[RULPrediction]:
        """Predict RUL with confidence intervals."""
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        X = X[self.feature_names]
        X_scaled = self.scaler.transform(X)

        # Get predictions
        rul_pred = self.model.predict(X_scaled)
        rul_lower = self.model_lower.predict(X_scaled)
        rul_upper = self.model_upper.predict(X_scaled)

        results = []
        now = datetime.utcnow()

        for i in range(len(X)):
            # Clamp predictions
            rul_days = max(self.min_rul, min(self.max_rul, int(rul_pred[i])))
            lower = max(self.min_rul, int(rul_lower[i]))
            upper = min(self.max_rul, int(rul_upper[i]))

            # Ensure bounds make sense
            lower = min(lower, rul_days)
            upper = max(upper, rul_days)

            # Calculate confidence based on interval width
            interval_width = upper - lower
            max_reasonable_width = 60  # days
            confidence = max(0.5, 1.0 - (interval_width / max_reasonable_width))

            # Determine health trend
            if rul_days <= 7:
                trend = "critical"
            elif rul_days <= 30:
                trend = "degrading"
            elif rul_days <= 90:
                trend = "stable"
            else:
                trend = "improving"

            result = RULPrediction(
                rul_days=rul_days,
                rul_hours=rul_days * 24,
                predicted_failure_date=now + timedelta(days=rul_days),
                confidence_score=confidence,
                confidence_interval_lower=lower,
                confidence_interval_upper=upper,
                health_trend=trend,
                contributing_features=self.feature_importances_,
                model_version=self.model_version,
                timestamp=now
            )
            results.append(result)

        return results

    def predict_single(self, features: Dict[str, float]) -> RULPrediction:
        """Predict RUL for single sample."""
        df = pd.DataFrame([features])
        return self.predict(df)[0]


class ExponentialDegradationRUL(RULPredictor):
    """
    Physics-informed RUL model assuming exponential degradation.

    Good for:
    - Equipment with known degradation patterns
    - Limited training data
    - Interpretable predictions

    Models health as: H(t) = H0 * exp(-lambda * t)
    Where lambda is the degradation rate.
    """

    def __init__(
        self,
        model_version: str = "1.0.0",
        failure_threshold: float = 0.3,  # Health level at failure
    ):
        super().__init__(model_version)
        self.failure_threshold = failure_threshold
        self.degradation_rates: Dict[str, float] = {}
        self.baseline_values: Dict[str, float] = {}

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "ExponentialDegradationRUL":
        """
        Fit degradation model from historical data.

        Estimates degradation rate for each feature.
        """
        self.feature_names = list(X.columns)

        # For each feature, estimate degradation rate
        for col in X.columns:
            values = X[col].values
            rul_values = y.values

            # Simple linear regression in log space
            # log(H/H0) = -lambda * (RUL_max - RUL)
            # Assume RUL_max is maximum observed RUL
            rul_max = rul_values.max()

            # Filter valid values
            valid_mask = values > 0
            if valid_mask.sum() < 10:
                self.degradation_rates[col] = 0.01  # Default
                self.baseline_values[col] = float(values.mean()) if len(values) > 0 else 1.0
                continue

            log_values = np.log(values[valid_mask])
            time_since_new = rul_max - rul_values[valid_mask]

            # Fit linear regression
            if len(time_since_new) > 1 and time_since_new.std() > 0:
                slope = -np.cov(time_since_new, log_values)[0, 1] / (np.var(time_since_new) + 1e-10)
                self.degradation_rates[col] = max(0.001, float(slope))
            else:
                self.degradation_rates[col] = 0.01

            # Baseline is initial healthy value
            self.baseline_values[col] = float(np.percentile(values[valid_mask], 90))

        self.is_fitted = True
        return self

    def predict(self, X: pd.DataFrame) -> List[RULPrediction]:
        """Predict RUL based on current health indicators."""
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        results = []
        now = datetime.utcnow()

        for i, row in X.iterrows():
            rul_estimates = []
            contributions = {}

            for col in self.feature_names:
                current_value = row[col]
                baseline = self.baseline_values.get(col, 1.0)
                rate = self.degradation_rates.get(col, 0.01)

                if current_value <= 0 or baseline <= 0:
                    continue

                # Current health ratio
                health_ratio = current_value / baseline

                # Time to failure threshold
                # H(t) = H0 * exp(-lambda * t)
                # t = -ln(H/H0) / lambda
                if health_ratio > self.failure_threshold:
                    rul_feature = -np.log(self.failure_threshold / health_ratio) / rate
                    rul_estimates.append(max(0, rul_feature))
                    contributions[col] = 1.0 / (rul_feature + 1)
                else:
                    rul_estimates.append(0)
                    contributions[col] = 1.0

            if not rul_estimates:
                rul_days = self.max_rul
            else:
                # Use minimum RUL across features (weakest link)
                rul_days = int(min(rul_estimates))

            # Normalize contributions
            total_contrib = sum(contributions.values())
            if total_contrib > 0:
                contributions = {k: v / total_contrib for k, v in contributions.items()}

            # Confidence based on consistency of estimates
            if len(rul_estimates) > 1:
                std_rul = np.std(rul_estimates)
                confidence = max(0.5, 1.0 - std_rul / (np.mean(rul_estimates) + 1))
            else:
                confidence = 0.7

            # Simple confidence interval
            lower = max(0, int(rul_days * 0.7))
            upper = min(self.max_rul, int(rul_days * 1.3))

            # Health trend
            if rul_days <= 7:
                trend = "critical"
            elif rul_days <= 30:
                trend = "degrading"
            elif rul_days <= 90:
                trend = "stable"
            else:
                trend = "improving"

            result = RULPrediction(
                rul_days=rul_days,
                rul_hours=rul_days * 24,
                predicted_failure_date=now + timedelta(days=rul_days),
                confidence_score=confidence,
                confidence_interval_lower=lower,
                confidence_interval_upper=upper,
                health_trend=trend,
                contributing_features=contributions,
                model_version=self.model_version,
                timestamp=now
            )
            results.append(result)

        return results

    def predict_single(self, features: Dict[str, float]) -> RULPrediction:
        """Predict RUL for single sample."""
        df = pd.DataFrame([features])
        return self.predict(df)[0]


class EnsembleRULPredictor(RULPredictor):
    """
    Ensemble of RUL predictors for robust predictions.

    Combines multiple models with weighted averaging.
    """

    def __init__(
        self,
        model_version: str = "1.0.0",
        predictors: Optional[List[RULPredictor]] = None,
        weights: Optional[List[float]] = None
    ):
        super().__init__(model_version)

        if predictors is None:
            self.predictors = [
                GradientBoostingRUL(),
                ExponentialDegradationRUL()
            ]
        else:
            self.predictors = predictors

        if weights is None:
            self.weights = [1.0 / len(self.predictors)] * len(self.predictors)
        else:
            total = sum(weights)
            self.weights = [w / total for w in weights]

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "EnsembleRULPredictor":
        """Train all predictors."""
        self.feature_names = list(X.columns)

        for predictor in self.predictors:
            predictor.fit(X, y)

        self.is_fitted = True
        return self

    def predict(self, X: pd.DataFrame) -> List[RULPrediction]:
        """Combine predictions from all models."""
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        all_predictions = [p.predict(X) for p in self.predictors]

        combined = []
        now = datetime.utcnow()

        for i in range(len(X)):
            # Weighted average
            rul_days = int(sum(
                w * pred[i].rul_days for w, pred in zip(self.weights, all_predictions)
            ))

            lower = int(sum(
                w * pred[i].confidence_interval_lower
                for w, pred in zip(self.weights, all_predictions)
            ))

            upper = int(sum(
                w * pred[i].confidence_interval_upper
                for w, pred in zip(self.weights, all_predictions)
            ))

            confidence = sum(
                w * pred[i].confidence_score
                for w, pred in zip(self.weights, all_predictions)
            )

            # Combine feature contributions
            all_contrib = {}
            for pred in all_predictions:
                for k, v in pred[i].contributing_features.items():
                    all_contrib[k] = all_contrib.get(k, 0) + v
            total = sum(all_contrib.values())
            if total > 0:
                all_contrib = {k: v / total for k, v in all_contrib.items()}

            if rul_days <= 7:
                trend = "critical"
            elif rul_days <= 30:
                trend = "degrading"
            elif rul_days <= 90:
                trend = "stable"
            else:
                trend = "improving"

            result = RULPrediction(
                rul_days=rul_days,
                rul_hours=rul_days * 24,
                predicted_failure_date=now + timedelta(days=rul_days),
                confidence_score=confidence,
                confidence_interval_lower=lower,
                confidence_interval_upper=upper,
                health_trend=trend,
                contributing_features=all_contrib,
                model_version=self.model_version,
                timestamp=now
            )
            combined.append(result)

        return combined

    def predict_single(self, features: Dict[str, float]) -> RULPrediction:
        """Predict RUL for single sample."""
        df = pd.DataFrame([features])
        return self.predict(df)[0]
