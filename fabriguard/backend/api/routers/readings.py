"""
Sensor Readings Router

Handles sensor data ingestion and retrieval.
"""
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import uuid

from api.database import get_db
from api.routers.auth import get_current_active_user
from models.user import User
from models.sensor import Sensor, SensorStatus
from models.reading import SensorReading
from models.asset import Asset

router = APIRouter()


# Pydantic Models
class ReadingCreate(BaseModel):
    """Single sensor reading for ingestion."""
    sensor_id: uuid.UUID
    timestamp: datetime
    value: float
    unit: str
    value_x: Optional[float] = None
    value_y: Optional[float] = None
    value_z: Optional[float] = None
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    value_avg: Optional[float] = None
    value_rms: Optional[float] = None
    value_std: Optional[float] = None
    sample_count: int = 1
    peak_frequency_hz: Optional[float] = None
    quality_score: float = 1.0
    anomaly_score: Optional[float] = None
    edge_processed: bool = False
    edge_gateway_id: Optional[str] = None
    features: Optional[dict] = None


class BatchReadingCreate(BaseModel):
    """Batch of sensor readings for efficient ingestion."""
    readings: List[ReadingCreate] = Field(..., min_length=1, max_length=1000)


class ReadingResponse(BaseModel):
    id: uuid.UUID
    sensor_id: uuid.UUID
    timestamp: datetime
    value: float
    unit: str
    value_x: Optional[float]
    value_y: Optional[float]
    value_z: Optional[float]
    value_rms: Optional[float]
    quality_score: float
    anomaly_score: Optional[float]
    is_valid: bool

    class Config:
        from_attributes = True


class ReadingListResponse(BaseModel):
    items: List[ReadingResponse]
    total: int
    sensor_id: uuid.UUID


class AggregatedReading(BaseModel):
    """Aggregated reading for time-series display."""
    timestamp: datetime
    value_avg: float
    value_min: float
    value_max: float
    value_rms: Optional[float]
    sample_count: int


class SensorTimeSeriesResponse(BaseModel):
    sensor_id: uuid.UUID
    sensor_name: str
    unit: str
    data: List[AggregatedReading]
    start_time: datetime
    end_time: datetime
    total_points: int


class GatewayHeartbeat(BaseModel):
    """Heartbeat from edge gateway."""
    gateway_id: str
    timestamp: datetime
    sensor_ids: List[uuid.UUID]
    battery_levels: Optional[dict] = None
    signal_strengths: Optional[dict] = None
    firmware_version: Optional[str] = None


# Routes
@router.post("/ingest", status_code=201)
async def ingest_readings(
    data: BatchReadingCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Ingest sensor readings from edge gateway.

    This endpoint is designed for high-throughput batch ingestion.
    Authentication is handled via API key (in production).
    """
    # Group readings by sensor for validation
    sensor_ids = set(r.sensor_id for r in data.readings)

    # Verify sensors exist
    sensors_result = await db.execute(
        select(Sensor).where(Sensor.id.in_(sensor_ids))
    )
    sensors = {s.id: s for s in sensors_result.scalars().all()}

    if len(sensors) != len(sensor_ids):
        missing = sensor_ids - set(sensors.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown sensor IDs: {missing}"
        )

    # Create reading records
    readings = []
    now = datetime.now(timezone.utc)

    for r in data.readings:
        sensor = sensors[r.sensor_id]

        reading = SensorReading(
            sensor_id=r.sensor_id,
            timestamp=r.timestamp,
            value=r.value,
            unit=r.unit,
            value_x=r.value_x,
            value_y=r.value_y,
            value_z=r.value_z,
            value_min=r.value_min,
            value_max=r.value_max,
            value_avg=r.value_avg,
            value_rms=r.value_rms,
            value_std=r.value_std,
            sample_count=r.sample_count,
            peak_frequency_hz=r.peak_frequency_hz,
            quality_score=r.quality_score,
            anomaly_score=r.anomaly_score,
            edge_processed=r.edge_processed,
            edge_gateway_id=r.edge_gateway_id,
            features=r.features,
            is_valid=r.quality_score > 0.5
        )
        readings.append(reading)

        # Update sensor last communication
        sensor.last_communication = now
        sensor.status = SensorStatus.ACTIVE

    db.add_all(readings)
    await db.commit()

    return {
        "message": "Readings ingested successfully",
        "count": len(readings),
        "sensors_updated": len(sensors)
    }


@router.post("/gateway/heartbeat")
async def gateway_heartbeat(
    data: GatewayHeartbeat,
    db: AsyncSession = Depends(get_db)
):
    """
    Process heartbeat from edge gateway.

    Updates sensor status and battery levels.
    """
    now = datetime.now(timezone.utc)

    # Update sensors
    if data.sensor_ids:
        sensors_result = await db.execute(
            select(Sensor).where(Sensor.id.in_(data.sensor_ids))
        )
        sensors = sensors_result.scalars().all()

        for sensor in sensors:
            sensor.last_communication = now
            sensor.gateway_id = data.gateway_id

            if data.battery_levels and str(sensor.id) in data.battery_levels:
                sensor.battery_level = data.battery_levels[str(sensor.id)]
                if sensor.battery_level < sensor.low_battery_threshold:
                    sensor.status = SensorStatus.LOW_BATTERY
                else:
                    sensor.status = SensorStatus.ACTIVE

            if data.signal_strengths and str(sensor.id) in data.signal_strengths:
                sensor.signal_strength = data.signal_strengths[str(sensor.id)]

        await db.commit()

    return {
        "message": "Heartbeat processed",
        "gateway_id": data.gateway_id,
        "sensors_updated": len(data.sensor_ids)
    }


@router.get("/sensor/{sensor_id}", response_model=ReadingListResponse)
async def get_sensor_readings(
    sensor_id: uuid.UUID,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=10000),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get raw sensor readings."""
    # Verify access
    sensor_result = await db.execute(
        select(Sensor)
        .join(Asset)
        .where(
            and_(
                Sensor.id == sensor_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    sensor = sensor_result.scalar_one_or_none()
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")

    # Default time range
    if not end_time:
        end_time = datetime.now(timezone.utc)
    if not start_time:
        start_time = end_time - timedelta(hours=24)

    query = (
        select(SensorReading)
        .where(SensorReading.sensor_id == sensor_id)
        .where(SensorReading.timestamp >= start_time)
        .where(SensorReading.timestamp <= end_time)
        .order_by(SensorReading.timestamp.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    readings = result.scalars().all()

    return ReadingListResponse(
        items=readings,
        total=len(readings),
        sensor_id=sensor_id
    )


@router.get("/sensor/{sensor_id}/timeseries", response_model=SensorTimeSeriesResponse)
async def get_sensor_timeseries(
    sensor_id: uuid.UUID,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    resolution: str = Query("5m", regex="^(1m|5m|15m|1h|6h|1d)$"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get aggregated time-series data for a sensor.

    Resolution options: 1m, 5m, 15m, 1h, 6h, 1d
    """
    # Verify access
    sensor_result = await db.execute(
        select(Sensor)
        .join(Asset)
        .where(
            and_(
                Sensor.id == sensor_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    sensor = sensor_result.scalar_one_or_none()
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")

    # Default time range based on resolution
    if not end_time:
        end_time = datetime.now(timezone.utc)

    resolution_defaults = {
        "1m": timedelta(hours=1),
        "5m": timedelta(hours=6),
        "15m": timedelta(hours=24),
        "1h": timedelta(days=7),
        "6h": timedelta(days=30),
        "1d": timedelta(days=90)
    }

    if not start_time:
        start_time = end_time - resolution_defaults.get(resolution, timedelta(hours=24))

    # For now, return raw readings (in production, use time-series DB aggregation)
    query = (
        select(SensorReading)
        .where(SensorReading.sensor_id == sensor_id)
        .where(SensorReading.timestamp >= start_time)
        .where(SensorReading.timestamp <= end_time)
        .order_by(SensorReading.timestamp.asc())
        .limit(1000)
    )

    result = await db.execute(query)
    readings = result.scalars().all()

    # Simple aggregation (in production, use proper time bucketing)
    data = [
        AggregatedReading(
            timestamp=r.timestamp,
            value_avg=float(r.value_avg or r.value),
            value_min=float(r.value_min or r.value),
            value_max=float(r.value_max or r.value),
            value_rms=float(r.value_rms) if r.value_rms else None,
            sample_count=r.sample_count
        )
        for r in readings
    ]

    return SensorTimeSeriesResponse(
        sensor_id=sensor_id,
        sensor_name=sensor.name,
        unit=sensor.measurement_unit,
        data=data,
        start_time=start_time,
        end_time=end_time,
        total_points=len(data)
    )


@router.get("/asset/{asset_id}/latest")
async def get_asset_latest_readings(
    asset_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get latest readings from all sensors on an asset."""
    # Verify access
    asset_result = await db.execute(
        select(Asset).where(
            and_(
                Asset.id == asset_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    asset = asset_result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Get sensors
    sensors_result = await db.execute(
        select(Sensor).where(Sensor.asset_id == asset_id)
    )
    sensors = sensors_result.scalars().all()

    latest_readings = {}
    for sensor in sensors:
        reading_result = await db.execute(
            select(SensorReading)
            .where(SensorReading.sensor_id == sensor.id)
            .order_by(SensorReading.timestamp.desc())
            .limit(1)
        )
        reading = reading_result.scalar_one_or_none()

        latest_readings[str(sensor.id)] = {
            "sensor_name": sensor.name,
            "sensor_type": sensor.sensor_type.value,
            "unit": sensor.measurement_unit,
            "status": sensor.status.value,
            "reading": {
                "value": float(reading.value),
                "timestamp": reading.timestamp.isoformat(),
                "quality_score": float(reading.quality_score),
                "anomaly_score": float(reading.anomaly_score) if reading.anomaly_score else None
            } if reading else None
        }

    return {
        "asset_id": str(asset_id),
        "asset_name": asset.name,
        "sensors": latest_readings
    }
