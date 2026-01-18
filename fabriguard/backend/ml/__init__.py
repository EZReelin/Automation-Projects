# FabriGuard ML Module
"""
Machine Learning models for predictive maintenance.

Includes:
- Anomaly detection (Isolation Forest, statistical methods)
- Remaining Useful Life (RUL) prediction
- Failure mode classification
- Health score calculation
"""

from .models.anomaly_detector import AnomalyDetector, IsolationForestDetector
from .models.rul_predictor import RULPredictor, GradientBoostingRUL
from .models.health_scorer import HealthScorer
from .features.extractor import FeatureExtractor
from .inference.engine import InferenceEngine

__all__ = [
    "AnomalyDetector",
    "IsolationForestDetector",
    "RULPredictor",
    "GradientBoostingRUL",
    "HealthScorer",
    "FeatureExtractor",
    "InferenceEngine"
]
