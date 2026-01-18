"""
Edge Gateway Processor

Handles local data processing, anomaly pre-filtering, and
data aggregation before cloud upload. Designed to run on
edge devices like Raspberry Pi or industrial gateways.
"""

import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import deque
import json
import asyncio
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ProcessedReading:
    """Processed sensor reading ready for upload."""
    sensor_id: str
    timestamp: datetime
    value: float
    value_min: float
    value_max: float
    value_avg: float
    value_rms: float
    value_std: float
    sample_count: int
    unit: str
    quality_score: float
    anomaly_score: float
    is_anomaly: bool
    peak_frequency_hz: Optional[float] = None
    features: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result


class EdgeProcessor:
    """
    Local edge processing for sensor data.

    Performs:
    - Data aggregation and compression
    - Real-time anomaly pre-filtering
    - Feature extraction
    - Quality scoring
    - Store-and-forward buffering
    """

    def __init__(
        self,
        gateway_id: str,
        buffer_size: int = 1000,
        aggregation_window_seconds: int = 60,
        anomaly_threshold: float = 3.0,  # Z-score threshold
        upload_interval_seconds: int = 300
    ):
        self.gateway_id = gateway_id
        self.buffer_size = buffer_size
        self.aggregation_window = aggregation_window_seconds
        self.anomaly_threshold = anomaly_threshold
        self.upload_interval = upload_interval_seconds

        # Sensor data buffers
        self.raw_buffers: Dict[str, deque] = {}
        self.processed_buffer: deque = deque(maxlen=buffer_size)

        # Baseline statistics per sensor (learned from initial data)
        self.baselines: Dict[str, Dict[str, float]] = {}

        # Processing state
        self.last_upload_time = datetime.utcnow()
        self.readings_processed = 0
        self.anomalies_detected = 0

    def add_reading(
        self,
        sensor_id: str,
        value: float,
        timestamp: Optional[datetime] = None,
        unit: str = ""
    ):
        """
        Add a raw sensor reading to the buffer.

        Args:
            sensor_id: Unique sensor identifier
            value: Sensor reading value
            timestamp: Reading timestamp (defaults to now)
            unit: Unit of measurement
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        # Initialize buffer if needed
        if sensor_id not in self.raw_buffers:
            self.raw_buffers[sensor_id] = deque(maxlen=10000)

        self.raw_buffers[sensor_id].append({
            'value': value,
            'timestamp': timestamp,
            'unit': unit
        })

    def process_sensor(self, sensor_id: str) -> Optional[ProcessedReading]:
        """
        Process buffered readings for a sensor.

        Aggregates data and performs anomaly detection.
        """
        if sensor_id not in self.raw_buffers:
            return None

        buffer = self.raw_buffers[sensor_id]
        if len(buffer) < 10:  # Need minimum data
            return None

        # Get readings within aggregation window
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=self.aggregation_window)

        readings = [
            r for r in buffer
            if r['timestamp'] >= window_start
        ]

        if not readings:
            return None

        values = np.array([r['value'] for r in readings])
        unit = readings[0]['unit']

        # Compute statistics
        value_avg = float(np.mean(values))
        value_std = float(np.std(values))
        value_min = float(np.min(values))
        value_max = float(np.max(values))
        value_rms = float(np.sqrt(np.mean(values**2)))

        # Quality score based on data completeness and consistency
        expected_samples = self.aggregation_window * 10  # Assuming 10 Hz min
        completeness = min(1.0, len(values) / expected_samples)

        # Check for stuck sensor (no variation)
        if value_std < 1e-10:
            quality_score = 0.5 * completeness
        else:
            quality_score = completeness

        # Anomaly detection using baseline comparison
        anomaly_score, is_anomaly = self._detect_anomaly(
            sensor_id, value_avg, value_std, value_rms
        )

        # Extract simple frequency features (if enough samples)
        peak_freq = None
        if len(values) >= 64:
            peak_freq = self._extract_peak_frequency(values)

        processed = ProcessedReading(
            sensor_id=sensor_id,
            timestamp=now,
            value=float(values[-1]),
            value_min=value_min,
            value_max=value_max,
            value_avg=value_avg,
            value_rms=value_rms,
            value_std=value_std,
            sample_count=len(values),
            unit=unit,
            quality_score=quality_score,
            anomaly_score=anomaly_score,
            is_anomaly=is_anomaly,
            peak_frequency_hz=peak_freq
        )

        self.processed_buffer.append(processed)
        self.readings_processed += 1

        if is_anomaly:
            self.anomalies_detected += 1
            logger.warning(
                "Anomaly detected",
                sensor_id=sensor_id,
                anomaly_score=anomaly_score,
                value=value_avg
            )

        # Clear processed readings from raw buffer
        self.raw_buffers[sensor_id].clear()

        return processed

    def _detect_anomaly(
        self,
        sensor_id: str,
        value_avg: float,
        value_std: float,
        value_rms: float
    ) -> Tuple[float, bool]:
        """
        Detect anomalies using statistical methods.

        Returns (anomaly_score, is_anomaly).
        """
        # Initialize baseline if not exists
        if sensor_id not in self.baselines:
            self.baselines[sensor_id] = {
                'mean': value_avg,
                'std': max(value_std, 0.001),
                'rms': value_rms,
                'samples': 1
            }
            return 0.0, False

        baseline = self.baselines[sensor_id]

        # Calculate z-score
        if baseline['std'] > 0:
            z_score = abs(value_avg - baseline['mean']) / baseline['std']
        else:
            z_score = 0.0

        # RMS comparison
        if baseline['rms'] > 0:
            rms_ratio = value_rms / baseline['rms']
        else:
            rms_ratio = 1.0

        # Combine into anomaly score (0-1)
        z_component = min(1.0, z_score / (self.anomaly_threshold * 2))
        rms_component = min(1.0, abs(rms_ratio - 1.0))
        anomaly_score = (z_component + rms_component) / 2

        is_anomaly = z_score > self.anomaly_threshold or rms_ratio > 2.0 or rms_ratio < 0.5

        # Update baseline with exponential moving average (slow adaptation)
        alpha = 0.01
        if not is_anomaly:
            baseline['mean'] = alpha * value_avg + (1 - alpha) * baseline['mean']
            baseline['std'] = alpha * value_std + (1 - alpha) * baseline['std']
            baseline['rms'] = alpha * value_rms + (1 - alpha) * baseline['rms']
            baseline['samples'] += 1

        return anomaly_score, is_anomaly

    def _extract_peak_frequency(
        self,
        values: np.ndarray,
        sampling_rate: float = 1000
    ) -> Optional[float]:
        """Extract dominant frequency using FFT."""
        try:
            from scipy.fft import fft, fftfreq

            n = len(values)
            fft_vals = fft(values)
            freqs = fftfreq(n, 1/sampling_rate)

            # Get positive frequencies
            pos_mask = freqs > 0
            magnitudes = np.abs(fft_vals[pos_mask])
            pos_freqs = freqs[pos_mask]

            # Find peak
            peak_idx = np.argmax(magnitudes)
            return float(pos_freqs[peak_idx])
        except Exception:
            return None

    def process_all_sensors(self) -> List[ProcessedReading]:
        """Process all sensors with buffered data."""
        results = []
        for sensor_id in list(self.raw_buffers.keys()):
            processed = self.process_sensor(sensor_id)
            if processed:
                results.append(processed)
        return results

    def get_upload_batch(self) -> List[Dict[str, Any]]:
        """
        Get batch of processed readings for upload.

        Returns list of readings and clears the processed buffer.
        """
        batch = []
        while self.processed_buffer:
            reading = self.processed_buffer.popleft()
            batch.append(reading.to_dict())

        self.last_upload_time = datetime.utcnow()
        return batch

    def should_upload(self) -> bool:
        """Check if it's time to upload data."""
        elapsed = (datetime.utcnow() - self.last_upload_time).total_seconds()
        return elapsed >= self.upload_interval or len(self.processed_buffer) >= self.buffer_size * 0.8

    def get_status(self) -> Dict[str, Any]:
        """Get processor status for monitoring."""
        return {
            'gateway_id': self.gateway_id,
            'sensors_active': len(self.raw_buffers),
            'readings_processed': self.readings_processed,
            'anomalies_detected': self.anomalies_detected,
            'buffer_size': len(self.processed_buffer),
            'last_upload': self.last_upload_time.isoformat(),
            'baselines_learned': len(self.baselines)
        }

    def reset_baselines(self, sensor_id: Optional[str] = None):
        """Reset learned baselines."""
        if sensor_id:
            if sensor_id in self.baselines:
                del self.baselines[sensor_id]
        else:
            self.baselines.clear()


class EdgeGateway:
    """
    Main edge gateway controller.

    Coordinates sensor data collection, processing, and upload.
    """

    def __init__(
        self,
        gateway_id: str,
        cloud_endpoint: str,
        api_key: str
    ):
        self.gateway_id = gateway_id
        self.cloud_endpoint = cloud_endpoint
        self.api_key = api_key

        self.processor = EdgeProcessor(gateway_id)
        self.running = False

        # Sensor registry
        self.sensors: Dict[str, Dict[str, Any]] = {}

    def register_sensor(
        self,
        sensor_id: str,
        sensor_type: str,
        asset_id: str,
        unit: str
    ):
        """Register a sensor with the gateway."""
        self.sensors[sensor_id] = {
            'sensor_type': sensor_type,
            'asset_id': asset_id,
            'unit': unit,
            'registered_at': datetime.utcnow().isoformat()
        }
        logger.info("Sensor registered", sensor_id=sensor_id, sensor_type=sensor_type)

    def ingest_reading(
        self,
        sensor_id: str,
        value: float,
        timestamp: Optional[datetime] = None
    ):
        """Ingest a sensor reading."""
        if sensor_id not in self.sensors:
            logger.warning("Unknown sensor", sensor_id=sensor_id)
            return

        unit = self.sensors[sensor_id]['unit']
        self.processor.add_reading(sensor_id, value, timestamp, unit)

    async def run(self):
        """Main processing loop."""
        self.running = True
        logger.info("Edge gateway started", gateway_id=self.gateway_id)

        while self.running:
            try:
                # Process all sensors
                self.processor.process_all_sensors()

                # Check if upload needed
                if self.processor.should_upload():
                    await self._upload_batch()

                # Send heartbeat
                await self._send_heartbeat()

                await asyncio.sleep(1)

            except Exception as e:
                logger.error("Processing error", error=str(e))
                await asyncio.sleep(5)

    async def _upload_batch(self):
        """Upload processed data to cloud."""
        batch = self.processor.get_upload_batch()
        if not batch:
            return

        # In production, this would use aiohttp to POST to cloud API
        logger.info(
            "Uploading batch",
            readings_count=len(batch),
            endpoint=self.cloud_endpoint
        )

        # Simulated upload
        # async with aiohttp.ClientSession() as session:
        #     async with session.post(
        #         f"{self.cloud_endpoint}/api/v1/readings/ingest",
        #         json={"readings": batch},
        #         headers={"Authorization": f"Bearer {self.api_key}"}
        #     ) as response:
        #         if response.status != 201:
        #             logger.error("Upload failed", status=response.status)

    async def _send_heartbeat(self):
        """Send heartbeat to cloud."""
        status = self.processor.get_status()
        status['sensor_ids'] = list(self.sensors.keys())

        # In production, POST to heartbeat endpoint
        logger.debug("Heartbeat", **status)

    def stop(self):
        """Stop the gateway."""
        self.running = False
        logger.info("Edge gateway stopped", gateway_id=self.gateway_id)
