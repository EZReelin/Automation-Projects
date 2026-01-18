"""
Feature Extraction for Predictive Maintenance

Extracts meaningful features from raw sensor data for ML models.
Includes time-domain, frequency-domain, and statistical features.
"""

from typing import Dict, List, Optional, Any, Tuple
import numpy as np
import pandas as pd
from scipy import stats, signal
from scipy.fft import fft, fftfreq
from dataclasses import dataclass


@dataclass
class ExtractedFeatures:
    """Container for extracted features."""
    features: Dict[str, float]
    metadata: Dict[str, Any]
    quality_score: float
    timestamp: str


class FeatureExtractor:
    """
    Extracts features from sensor data for predictive maintenance.

    Supports:
    - Time-domain statistics (mean, std, RMS, peak, crest factor)
    - Frequency-domain features (FFT peaks, spectral energy)
    - Trend features (slope, curvature)
    - Cross-sensor correlations
    """

    def __init__(
        self,
        sampling_rate: float = 1000.0,  # Hz
        window_size: int = 1024,
        overlap: float = 0.5
    ):
        self.sampling_rate = sampling_rate
        self.window_size = window_size
        self.overlap = overlap

    def extract_all(
        self,
        data: pd.DataFrame,
        sensor_configs: Optional[Dict[str, Dict]] = None
    ) -> ExtractedFeatures:
        """
        Extract all features from sensor data.

        Args:
            data: DataFrame with sensor readings (columns are sensors)
            sensor_configs: Optional config per sensor (type, units, etc.)

        Returns:
            ExtractedFeatures with all computed features
        """
        features = {}
        quality_scores = []

        for col in data.columns:
            values = data[col].dropna().values

            if len(values) < 10:
                continue

            # Time-domain features
            time_features = self.extract_time_domain(values, col)
            features.update(time_features)

            # Frequency-domain features (for vibration sensors)
            if sensor_configs:
                sensor_type = sensor_configs.get(col, {}).get("type", "")
                if "vibration" in sensor_type.lower():
                    freq_features = self.extract_frequency_domain(values, col)
                    features.update(freq_features)

            # Quality score based on data completeness
            quality = len(values) / len(data)
            quality_scores.append(quality)

        # Add cross-sensor features if multiple sensors
        if len(data.columns) > 1:
            cross_features = self.extract_cross_sensor(data)
            features.update(cross_features)

        overall_quality = np.mean(quality_scores) if quality_scores else 0.0

        return ExtractedFeatures(
            features=features,
            metadata={
                "num_sensors": len(data.columns),
                "num_samples": len(data),
                "sampling_rate": self.sampling_rate
            },
            quality_score=overall_quality,
            timestamp=pd.Timestamp.now().isoformat()
        )

    def extract_time_domain(
        self,
        values: np.ndarray,
        prefix: str = ""
    ) -> Dict[str, float]:
        """
        Extract time-domain statistical features.

        Args:
            values: 1D array of sensor values
            prefix: Prefix for feature names

        Returns:
            Dict of feature names to values
        """
        if len(values) == 0:
            return {}

        prefix = f"{prefix}_" if prefix else ""

        features = {}

        # Basic statistics
        features[f"{prefix}mean"] = float(np.mean(values))
        features[f"{prefix}std"] = float(np.std(values))
        features[f"{prefix}var"] = float(np.var(values))
        features[f"{prefix}min"] = float(np.min(values))
        features[f"{prefix}max"] = float(np.max(values))
        features[f"{prefix}range"] = float(np.max(values) - np.min(values))

        # RMS (Root Mean Square) - important for vibration
        features[f"{prefix}rms"] = float(np.sqrt(np.mean(values**2)))

        # Peak value
        features[f"{prefix}peak"] = float(np.max(np.abs(values)))

        # Crest factor (peak / RMS) - indicator of impulsiveness
        rms = features[f"{prefix}rms"]
        if rms > 0:
            features[f"{prefix}crest_factor"] = features[f"{prefix}peak"] / rms
        else:
            features[f"{prefix}crest_factor"] = 0.0

        # Shape factor (RMS / mean absolute)
        mean_abs = np.mean(np.abs(values))
        if mean_abs > 0:
            features[f"{prefix}shape_factor"] = rms / mean_abs
        else:
            features[f"{prefix}shape_factor"] = 0.0

        # Percentiles
        features[f"{prefix}p5"] = float(np.percentile(values, 5))
        features[f"{prefix}p25"] = float(np.percentile(values, 25))
        features[f"{prefix}p50"] = float(np.percentile(values, 50))
        features[f"{prefix}p75"] = float(np.percentile(values, 75))
        features[f"{prefix}p95"] = float(np.percentile(values, 95))

        # IQR (Interquartile Range)
        features[f"{prefix}iqr"] = features[f"{prefix}p75"] - features[f"{prefix}p25"]

        # Skewness and Kurtosis
        if len(values) > 2:
            features[f"{prefix}skewness"] = float(stats.skew(values))
            features[f"{prefix}kurtosis"] = float(stats.kurtosis(values))
        else:
            features[f"{prefix}skewness"] = 0.0
            features[f"{prefix}kurtosis"] = 0.0

        # Zero crossing rate
        zero_crossings = np.sum(np.diff(np.signbit(values)))
        features[f"{prefix}zero_crossing_rate"] = float(zero_crossings / len(values))

        # Trend (linear regression slope)
        if len(values) > 1:
            x = np.arange(len(values))
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, values)
            features[f"{prefix}trend_slope"] = float(slope)
            features[f"{prefix}trend_r2"] = float(r_value**2)
        else:
            features[f"{prefix}trend_slope"] = 0.0
            features[f"{prefix}trend_r2"] = 0.0

        return features

    def extract_frequency_domain(
        self,
        values: np.ndarray,
        prefix: str = ""
    ) -> Dict[str, float]:
        """
        Extract frequency-domain features using FFT.

        Particularly useful for vibration analysis.

        Args:
            values: 1D array of sensor values
            prefix: Prefix for feature names

        Returns:
            Dict of frequency-domain features
        """
        if len(values) < self.window_size:
            return {}

        prefix = f"{prefix}_" if prefix else ""

        features = {}

        # Apply window function
        windowed = values[:self.window_size] * signal.windows.hann(self.window_size)

        # Compute FFT
        fft_values = fft(windowed)
        freqs = fftfreq(self.window_size, 1/self.sampling_rate)

        # Get positive frequencies only
        positive_mask = freqs >= 0
        fft_magnitude = np.abs(fft_values[positive_mask])
        positive_freqs = freqs[positive_mask]

        # Normalize
        fft_magnitude = fft_magnitude / len(fft_magnitude)

        # Spectral features
        features[f"{prefix}spectral_energy"] = float(np.sum(fft_magnitude**2))
        features[f"{prefix}spectral_mean"] = float(np.mean(fft_magnitude))
        features[f"{prefix}spectral_std"] = float(np.std(fft_magnitude))

        # Peak frequency
        peak_idx = np.argmax(fft_magnitude)
        features[f"{prefix}peak_frequency"] = float(positive_freqs[peak_idx])
        features[f"{prefix}peak_magnitude"] = float(fft_magnitude[peak_idx])

        # Top N peak frequencies
        n_peaks = 5
        peak_indices = np.argsort(fft_magnitude)[-n_peaks:][::-1]
        for i, idx in enumerate(peak_indices):
            features[f"{prefix}peak{i+1}_freq"] = float(positive_freqs[idx])
            features[f"{prefix}peak{i+1}_mag"] = float(fft_magnitude[idx])

        # Spectral centroid (center of mass of spectrum)
        if np.sum(fft_magnitude) > 0:
            spectral_centroid = np.sum(positive_freqs * fft_magnitude) / np.sum(fft_magnitude)
            features[f"{prefix}spectral_centroid"] = float(spectral_centroid)
        else:
            features[f"{prefix}spectral_centroid"] = 0.0

        # Spectral bandwidth
        if np.sum(fft_magnitude) > 0:
            centroid = features[f"{prefix}spectral_centroid"]
            spectral_bandwidth = np.sqrt(
                np.sum(((positive_freqs - centroid)**2) * fft_magnitude) / np.sum(fft_magnitude)
            )
            features[f"{prefix}spectral_bandwidth"] = float(spectral_bandwidth)
        else:
            features[f"{prefix}spectral_bandwidth"] = 0.0

        # Band energies (for vibration analysis)
        bands = [
            ("low", 0, 100),
            ("mid", 100, 500),
            ("high", 500, 2000),
            ("very_high", 2000, self.sampling_rate/2)
        ]

        total_energy = np.sum(fft_magnitude**2)
        for band_name, low, high in bands:
            band_mask = (positive_freqs >= low) & (positive_freqs < high)
            band_energy = np.sum(fft_magnitude[band_mask]**2)
            features[f"{prefix}band_{band_name}_energy"] = float(band_energy)
            if total_energy > 0:
                features[f"{prefix}band_{band_name}_ratio"] = float(band_energy / total_energy)
            else:
                features[f"{prefix}band_{band_name}_ratio"] = 0.0

        return features

    def extract_cross_sensor(self, data: pd.DataFrame) -> Dict[str, float]:
        """
        Extract features from relationships between sensors.

        Useful for detecting patterns that involve multiple sensors.
        """
        features = {}
        columns = list(data.columns)

        # Correlation matrix features
        if len(columns) > 1:
            corr_matrix = data.corr()

            # Average correlation
            upper_triangle = np.triu(corr_matrix.values, k=1)
            avg_corr = np.mean(upper_triangle[upper_triangle != 0])
            features["cross_avg_correlation"] = float(avg_corr) if not np.isnan(avg_corr) else 0.0

            # Max correlation (excluding self)
            np.fill_diagonal(corr_matrix.values, 0)
            features["cross_max_correlation"] = float(np.max(np.abs(corr_matrix.values)))

            # Specific sensor pair correlations
            for i, col1 in enumerate(columns):
                for col2 in columns[i+1:]:
                    corr = data[col1].corr(data[col2])
                    if not np.isnan(corr):
                        features[f"corr_{col1}_{col2}"] = float(corr)

        return features

    def extract_rolling_features(
        self,
        data: pd.DataFrame,
        window_minutes: int = 60
    ) -> pd.DataFrame:
        """
        Extract rolling window features for trend analysis.

        Args:
            data: Time-indexed DataFrame
            window_minutes: Rolling window size

        Returns:
            DataFrame with rolling features
        """
        window_size = int(window_minutes * 60 * self.sampling_rate / 1000)  # Convert to samples

        result = pd.DataFrame(index=data.index)

        for col in data.columns:
            # Rolling statistics
            result[f"{col}_rolling_mean"] = data[col].rolling(window_size).mean()
            result[f"{col}_rolling_std"] = data[col].rolling(window_size).std()
            result[f"{col}_rolling_min"] = data[col].rolling(window_size).min()
            result[f"{col}_rolling_max"] = data[col].rolling(window_size).max()

            # Rate of change
            result[f"{col}_rate_of_change"] = data[col].diff() / (1 / self.sampling_rate)

            # Acceleration (second derivative)
            result[f"{col}_acceleration"] = result[f"{col}_rate_of_change"].diff() / (1 / self.sampling_rate)

        return result.dropna()


class EquipmentFeatureExtractor:
    """
    Equipment-specific feature extraction.

    Provides specialized feature sets for different equipment types.
    """

    def __init__(self):
        self.extractors: Dict[str, FeatureExtractor] = {}
        self._initialize_extractors()

    def _initialize_extractors(self):
        """Initialize extractors with equipment-specific settings."""

        # CNC machines - high-frequency vibration monitoring
        self.extractors["cnc_machining_center"] = FeatureExtractor(
            sampling_rate=10000,  # 10 kHz for spindle monitoring
            window_size=2048
        )

        # Hydraulic press - lower frequency, pressure focus
        self.extractors["hydraulic_press"] = FeatureExtractor(
            sampling_rate=1000,
            window_size=1024
        )

        # Air compressor - moderate frequency
        self.extractors["air_compressor"] = FeatureExtractor(
            sampling_rate=5000,
            window_size=1024
        )

        # Default
        self.extractors["default"] = FeatureExtractor()

    def get_extractor(self, equipment_type: str) -> FeatureExtractor:
        """Get extractor for equipment type."""
        return self.extractors.get(equipment_type, self.extractors["default"])

    def extract(
        self,
        equipment_type: str,
        data: pd.DataFrame,
        sensor_configs: Optional[Dict] = None
    ) -> ExtractedFeatures:
        """Extract features using equipment-specific extractor."""
        extractor = self.get_extractor(equipment_type)
        return extractor.extract_all(data, sensor_configs)
