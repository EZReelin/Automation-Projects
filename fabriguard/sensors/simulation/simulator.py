"""
Sensor Data Simulator

Generates realistic sensor data for testing and demonstration
without requiring physical hardware. Supports various equipment
types and degradation scenarios.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json


class EquipmentState(str, Enum):
    """Equipment operating states."""
    HEALTHY = "healthy"
    DEGRADING = "degrading"
    WARNING = "warning"
    CRITICAL = "critical"
    FAILED = "failed"


@dataclass
class SensorConfig:
    """Configuration for a simulated sensor."""
    name: str
    sensor_type: str
    unit: str
    baseline_value: float
    noise_std: float
    min_value: float
    max_value: float
    sampling_rate_hz: float = 1000
    # Degradation parameters
    degradation_rate: float = 0.0  # Per day
    failure_threshold: float = 0.0


class SensorSimulator:
    """
    Simulates sensor data with realistic characteristics.

    Features:
    - Baseline normal operation
    - Gaussian noise
    - Gradual degradation
    - Anomaly injection
    - Equipment-specific patterns
    """

    def __init__(
        self,
        config: SensorConfig,
        random_seed: Optional[int] = None
    ):
        self.config = config
        self.rng = np.random.default_rng(random_seed)

        # State tracking
        self.current_value = config.baseline_value
        self.degradation_factor = 1.0
        self.operating_days = 0
        self.anomaly_active = False
        self.anomaly_magnitude = 0.0

    def generate_sample(self) -> float:
        """Generate a single sensor reading."""
        # Base value with degradation
        base = self.config.baseline_value * self.degradation_factor

        # Add noise
        noise = self.rng.normal(0, self.config.noise_std)

        # Add anomaly if active
        if self.anomaly_active:
            anomaly = self.anomaly_magnitude * self.config.baseline_value
        else:
            anomaly = 0.0

        value = base + noise + anomaly

        # Clamp to valid range
        value = np.clip(value, self.config.min_value, self.config.max_value)

        self.current_value = value
        return value

    def generate_timeseries(
        self,
        duration_seconds: float,
        include_timestamp: bool = True
    ) -> pd.DataFrame:
        """
        Generate a time series of sensor readings.

        Args:
            duration_seconds: Length of time series
            include_timestamp: Whether to include timestamp column

        Returns:
            DataFrame with sensor readings
        """
        n_samples = int(duration_seconds * self.config.sampling_rate_hz)
        values = [self.generate_sample() for _ in range(n_samples)]

        if include_timestamp:
            timestamps = pd.date_range(
                start=datetime.now(),
                periods=n_samples,
                freq=f'{1/self.config.sampling_rate_hz}S'
            )
            return pd.DataFrame({
                'timestamp': timestamps,
                self.config.name: values
            })
        else:
            return pd.DataFrame({self.config.name: values})

    def apply_degradation(self, days: float = 1.0):
        """
        Apply degradation over time.

        Args:
            days: Number of days of operation
        """
        self.operating_days += days
        self.degradation_factor *= (1 - self.config.degradation_rate * days)
        self.degradation_factor = max(0.1, self.degradation_factor)

    def inject_anomaly(self, magnitude: float = 0.2, duration_samples: int = 100):
        """
        Inject an anomaly into the sensor readings.

        Args:
            magnitude: Anomaly magnitude as fraction of baseline
            duration_samples: How long the anomaly lasts
        """
        self.anomaly_active = True
        self.anomaly_magnitude = magnitude

    def clear_anomaly(self):
        """Remove active anomaly."""
        self.anomaly_active = False
        self.anomaly_magnitude = 0.0

    def reset(self):
        """Reset sensor to initial state."""
        self.current_value = self.config.baseline_value
        self.degradation_factor = 1.0
        self.operating_days = 0
        self.anomaly_active = False
        self.anomaly_magnitude = 0.0


class EquipmentSimulator:
    """
    Simulates complete equipment with multiple sensors.

    Models realistic sensor correlations and equipment-specific
    behavior patterns.
    """

    def __init__(
        self,
        equipment_type: str,
        equipment_id: str,
        random_seed: Optional[int] = None
    ):
        self.equipment_type = equipment_type
        self.equipment_id = equipment_id
        self.rng = np.random.default_rng(random_seed)

        self.sensors: Dict[str, SensorSimulator] = {}
        self.state = EquipmentState.HEALTHY
        self.operating_hours = 0
        self.days_since_maintenance = 0

        # Initialize sensors based on equipment type
        self._initialize_sensors()

    def _initialize_sensors(self):
        """Initialize sensors based on equipment type."""
        sensor_configs = self._get_sensor_configs()
        for config in sensor_configs:
            self.sensors[config.name] = SensorSimulator(config, self.rng.integers(0, 10000))

    def _get_sensor_configs(self) -> List[SensorConfig]:
        """Get sensor configurations for equipment type."""

        if self.equipment_type == "cnc_machining_center":
            return [
                SensorConfig(
                    name="spindle_vibration_x",
                    sensor_type="vibration_triaxial",
                    unit="g",
                    baseline_value=0.05,
                    noise_std=0.01,
                    min_value=0.0,
                    max_value=10.0,
                    degradation_rate=0.001
                ),
                SensorConfig(
                    name="spindle_vibration_y",
                    sensor_type="vibration_triaxial",
                    unit="g",
                    baseline_value=0.05,
                    noise_std=0.01,
                    min_value=0.0,
                    max_value=10.0,
                    degradation_rate=0.001
                ),
                SensorConfig(
                    name="spindle_vibration_z",
                    sensor_type="vibration_triaxial",
                    unit="g",
                    baseline_value=0.03,
                    noise_std=0.008,
                    min_value=0.0,
                    max_value=10.0,
                    degradation_rate=0.0008
                ),
                SensorConfig(
                    name="spindle_temperature",
                    sensor_type="temperature_contact",
                    unit="C",
                    baseline_value=45.0,
                    noise_std=2.0,
                    min_value=20.0,
                    max_value=150.0,
                    degradation_rate=0.002
                ),
                SensorConfig(
                    name="spindle_current",
                    sensor_type="current_ct",
                    unit="A",
                    baseline_value=15.0,
                    noise_std=1.0,
                    min_value=0.0,
                    max_value=50.0,
                    degradation_rate=0.001
                ),
                SensorConfig(
                    name="coolant_flow",
                    sensor_type="flow_coolant",
                    unit="L/min",
                    baseline_value=10.0,
                    noise_std=0.5,
                    min_value=0.0,
                    max_value=20.0,
                    degradation_rate=0.0005
                ),
                SensorConfig(
                    name="coolant_temperature",
                    sensor_type="temperature_contact",
                    unit="C",
                    baseline_value=25.0,
                    noise_std=1.0,
                    min_value=15.0,
                    max_value=50.0,
                    degradation_rate=0.001
                )
            ]

        elif self.equipment_type == "hydraulic_press":
            return [
                SensorConfig(
                    name="hydraulic_pressure",
                    sensor_type="pressure_hydraulic",
                    unit="PSI",
                    baseline_value=3000.0,
                    noise_std=50.0,
                    min_value=0.0,
                    max_value=5000.0,
                    degradation_rate=0.002
                ),
                SensorConfig(
                    name="pump_vibration",
                    sensor_type="vibration_triaxial",
                    unit="g",
                    baseline_value=0.08,
                    noise_std=0.015,
                    min_value=0.0,
                    max_value=10.0,
                    degradation_rate=0.0015
                ),
                SensorConfig(
                    name="oil_temperature",
                    sensor_type="temperature_contact",
                    unit="C",
                    baseline_value=50.0,
                    noise_std=3.0,
                    min_value=20.0,
                    max_value=100.0,
                    degradation_rate=0.002
                ),
                SensorConfig(
                    name="motor_current",
                    sensor_type="current_ct",
                    unit="A",
                    baseline_value=25.0,
                    noise_std=2.0,
                    min_value=0.0,
                    max_value=60.0,
                    degradation_rate=0.001
                ),
                SensorConfig(
                    name="cylinder_position",
                    sensor_type="position",
                    unit="mm",
                    baseline_value=500.0,
                    noise_std=1.0,
                    min_value=0.0,
                    max_value=1000.0,
                    degradation_rate=0.0
                )
            ]

        elif self.equipment_type == "air_compressor":
            return [
                SensorConfig(
                    name="discharge_pressure",
                    sensor_type="pressure_pneumatic",
                    unit="PSI",
                    baseline_value=125.0,
                    noise_std=3.0,
                    min_value=0.0,
                    max_value=200.0,
                    degradation_rate=0.001
                ),
                SensorConfig(
                    name="intake_pressure",
                    sensor_type="pressure_pneumatic",
                    unit="PSI",
                    baseline_value=14.7,
                    noise_std=0.5,
                    min_value=10.0,
                    max_value=20.0,
                    degradation_rate=0.0
                ),
                SensorConfig(
                    name="motor_vibration",
                    sensor_type="vibration_triaxial",
                    unit="g",
                    baseline_value=0.1,
                    noise_std=0.02,
                    min_value=0.0,
                    max_value=10.0,
                    degradation_rate=0.001
                ),
                SensorConfig(
                    name="motor_temperature",
                    sensor_type="temperature_contact",
                    unit="C",
                    baseline_value=55.0,
                    noise_std=3.0,
                    min_value=20.0,
                    max_value=120.0,
                    degradation_rate=0.002
                ),
                SensorConfig(
                    name="motor_current",
                    sensor_type="current_ct",
                    unit="A",
                    baseline_value=20.0,
                    noise_std=1.5,
                    min_value=0.0,
                    max_value=50.0,
                    degradation_rate=0.001
                ),
                SensorConfig(
                    name="oil_level",
                    sensor_type="level",
                    unit="%",
                    baseline_value=90.0,
                    noise_std=2.0,
                    min_value=0.0,
                    max_value=100.0,
                    degradation_rate=0.003
                ),
                SensorConfig(
                    name="filter_dp",
                    sensor_type="pressure_differential",
                    unit="PSI",
                    baseline_value=2.0,
                    noise_std=0.3,
                    min_value=0.0,
                    max_value=20.0,
                    degradation_rate=0.005  # Filters clog over time
                )
            ]

        else:
            # Default generic sensors
            return [
                SensorConfig(
                    name="vibration",
                    sensor_type="vibration_triaxial",
                    unit="g",
                    baseline_value=0.1,
                    noise_std=0.02,
                    min_value=0.0,
                    max_value=10.0,
                    degradation_rate=0.001
                ),
                SensorConfig(
                    name="temperature",
                    sensor_type="temperature_contact",
                    unit="C",
                    baseline_value=40.0,
                    noise_std=2.0,
                    min_value=15.0,
                    max_value=100.0,
                    degradation_rate=0.002
                ),
                SensorConfig(
                    name="current",
                    sensor_type="current_ct",
                    unit="A",
                    baseline_value=10.0,
                    noise_std=1.0,
                    min_value=0.0,
                    max_value=50.0,
                    degradation_rate=0.001
                )
            ]

    def generate_readings(
        self,
        duration_seconds: float = 60,
        aggregate: bool = True
    ) -> Dict[str, Any]:
        """
        Generate sensor readings for all sensors.

        Args:
            duration_seconds: Duration of readings
            aggregate: Whether to aggregate into statistics

        Returns:
            Dict with sensor readings
        """
        readings = {}
        timestamp = datetime.utcnow()

        for name, simulator in self.sensors.items():
            if aggregate:
                # Generate and compute statistics
                data = simulator.generate_timeseries(duration_seconds, include_timestamp=False)
                values = data[name].values

                readings[name] = {
                    "value": float(values[-1]),
                    "min": float(np.min(values)),
                    "max": float(np.max(values)),
                    "mean": float(np.mean(values)),
                    "std": float(np.std(values)),
                    "rms": float(np.sqrt(np.mean(values**2))),
                    "unit": simulator.config.unit,
                    "sample_count": len(values)
                }
            else:
                readings[name] = {
                    "value": simulator.generate_sample(),
                    "unit": simulator.config.unit
                }

        return {
            "equipment_id": self.equipment_id,
            "equipment_type": self.equipment_type,
            "timestamp": timestamp.isoformat(),
            "state": self.state.value,
            "operating_hours": self.operating_hours,
            "readings": readings
        }

    def simulate_operation(self, hours: float = 8):
        """
        Simulate equipment operation over time.

        Args:
            hours: Hours of operation to simulate
        """
        days = hours / 24

        for simulator in self.sensors.values():
            simulator.apply_degradation(days)

        self.operating_hours += hours
        self.days_since_maintenance += days

        # Update state based on degradation
        self._update_state()

    def _update_state(self):
        """Update equipment state based on sensor values."""
        # Check degradation levels
        degradation_levels = [s.degradation_factor for s in self.sensors.values()]
        min_degradation = min(degradation_levels)

        if min_degradation > 0.9:
            self.state = EquipmentState.HEALTHY
        elif min_degradation > 0.7:
            self.state = EquipmentState.DEGRADING
        elif min_degradation > 0.5:
            self.state = EquipmentState.WARNING
        elif min_degradation > 0.3:
            self.state = EquipmentState.CRITICAL
        else:
            self.state = EquipmentState.FAILED

    def inject_failure_scenario(self, scenario: str):
        """
        Inject a failure scenario into the equipment.

        Args:
            scenario: Type of failure to inject
        """
        if scenario == "bearing_wear":
            # Increase vibration
            for name, sim in self.sensors.items():
                if "vibration" in name.lower():
                    sim.inject_anomaly(magnitude=0.5)

        elif scenario == "overheating":
            # Increase temperature
            for name, sim in self.sensors.items():
                if "temperature" in name.lower():
                    sim.inject_anomaly(magnitude=0.3)

        elif scenario == "motor_overload":
            # Increase current
            for name, sim in self.sensors.items():
                if "current" in name.lower():
                    sim.inject_anomaly(magnitude=0.25)

        elif scenario == "pump_failure":
            # Decrease pressure, increase vibration
            for name, sim in self.sensors.items():
                if "pressure" in name.lower():
                    sim.inject_anomaly(magnitude=-0.3)
                if "vibration" in name.lower():
                    sim.inject_anomaly(magnitude=0.4)

        elif scenario == "filter_clogged":
            # Increase filter differential pressure
            for name, sim in self.sensors.items():
                if "filter" in name.lower() or "dp" in name.lower():
                    sim.inject_anomaly(magnitude=2.0)

        self.state = EquipmentState.WARNING

    def clear_all_anomalies(self):
        """Clear all injected anomalies."""
        for simulator in self.sensors.values():
            simulator.clear_anomaly()

    def perform_maintenance(self):
        """Simulate maintenance being performed."""
        for simulator in self.sensors.values():
            simulator.reset()

        self.state = EquipmentState.HEALTHY
        self.days_since_maintenance = 0

    def get_health_metrics(self) -> Dict[str, Any]:
        """Get current health metrics for the equipment."""
        degradation_levels = {
            name: sim.degradation_factor
            for name, sim in self.sensors.items()
        }

        return {
            "equipment_id": self.equipment_id,
            "state": self.state.value,
            "operating_hours": self.operating_hours,
            "days_since_maintenance": self.days_since_maintenance,
            "overall_health": min(degradation_levels.values()) * 100,
            "sensor_health": degradation_levels
        }


class FleetSimulator:
    """
    Simulates a fleet of equipment for testing scenarios.
    """

    def __init__(self, random_seed: Optional[int] = None):
        self.equipment: Dict[str, EquipmentSimulator] = {}
        self.rng = np.random.default_rng(random_seed)

    def add_equipment(
        self,
        equipment_id: str,
        equipment_type: str
    ) -> EquipmentSimulator:
        """Add equipment to the fleet."""
        simulator = EquipmentSimulator(
            equipment_type=equipment_type,
            equipment_id=equipment_id,
            random_seed=self.rng.integers(0, 100000)
        )
        self.equipment[equipment_id] = simulator
        return simulator

    def generate_fleet_readings(self) -> List[Dict[str, Any]]:
        """Generate readings for all equipment in fleet."""
        return [eq.generate_readings() for eq in self.equipment.values()]

    def simulate_fleet_operation(self, hours: float = 8):
        """Simulate operation for all equipment."""
        for eq in self.equipment.values():
            eq.simulate_operation(hours)

    def get_fleet_health(self) -> List[Dict[str, Any]]:
        """Get health metrics for all equipment."""
        return [eq.get_health_metrics() for eq in self.equipment.values()]
