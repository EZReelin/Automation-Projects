"""
Sensors Router

Manages sensor CRUD operations and configuration.
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import uuid

from api.database import get_db
from api.routers.auth import get_current_active_user, require_role
from models.user import User, UserRole
from models.sensor import Sensor, SensorType, SensorStatus
from models.asset import Asset

router = APIRouter()


# Pydantic Models
class SensorBase(BaseModel):
    serial_number: str = Field(..., min_length=1, max_length=100)
    device_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    sensor_type: SensorType
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    installation_location: Optional[str] = None
    orientation: Optional[str] = None
    communication_protocol: str = "wifi"
    power_source: str = "battery"
    sampling_rate_hz: int = Field(default=1000, ge=1)
    sampling_interval_seconds: int = Field(default=60, ge=1)
    reporting_interval_seconds: int = Field(default=300, ge=1)
    measurement_unit: str
    measurement_range_min: Optional[float] = None
    measurement_range_max: Optional[float] = None
    threshold_warning_low: Optional[float] = None
    threshold_warning_high: Optional[float] = None
    threshold_critical_low: Optional[float] = None
    threshold_critical_high: Optional[float] = None


class SensorCreate(SensorBase):
    asset_id: uuid.UUID


class SensorUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    firmware_version: Optional[str] = None
    installation_location: Optional[str] = None
    orientation: Optional[str] = None
    sampling_rate_hz: Optional[int] = Field(None, ge=1)
    sampling_interval_seconds: Optional[int] = Field(None, ge=1)
    reporting_interval_seconds: Optional[int] = Field(None, ge=1)
    threshold_warning_low: Optional[float] = None
    threshold_warning_high: Optional[float] = None
    threshold_critical_low: Optional[float] = None
    threshold_critical_high: Optional[float] = None
    calibration_factor: Optional[float] = None
    calibration_offset: Optional[float] = None


class SensorResponse(SensorBase):
    id: uuid.UUID
    asset_id: uuid.UUID
    status: SensorStatus
    battery_level: Optional[int]
    signal_strength: Optional[int]
    last_communication: Optional[datetime]
    calibration_date: Optional[datetime]
    calibration_due_date: Optional[datetime]
    calibration_factor: float
    calibration_offset: float
    installation_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SensorListResponse(BaseModel):
    items: List[SensorResponse]
    total: int
    page: int
    page_size: int


class SensorStatusSummary(BaseModel):
    total_sensors: int
    active: int
    inactive: int
    error: int
    low_battery: int
    avg_battery_level: float


class SensorCalibration(BaseModel):
    calibration_factor: float = 1.0
    calibration_offset: float = 0.0
    calibration_notes: Optional[str] = None


# Routes
@router.get("", response_model=SensorListResponse)
async def list_sensors(
    asset_id: Optional[uuid.UUID] = None,
    sensor_type: Optional[SensorType] = None,
    status: Optional[SensorStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List all sensors for the user's organization."""
    # Build query joining through assets to filter by organization
    query = (
        select(Sensor)
        .join(Asset)
        .where(Asset.organization_id == current_user.organization_id)
    )

    if asset_id:
        query = query.where(Sensor.asset_id == asset_id)
    if sensor_type:
        query = query.where(Sensor.sensor_type == sensor_type)
    if status:
        query = query.where(Sensor.status == status)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # Apply pagination
    query = query.order_by(Sensor.name).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    sensors = result.scalars().all()

    return SensorListResponse(
        items=sensors,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/status-summary", response_model=SensorStatusSummary)
async def get_sensor_status_summary(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get aggregated status summary for all sensors."""
    # Query sensors through assets
    base_query = (
        select(Sensor)
        .join(Asset)
        .where(Asset.organization_id == current_user.organization_id)
    )

    # Status counts
    status_query = (
        select(Sensor.status, func.count(Sensor.id))
        .join(Asset)
        .where(Asset.organization_id == current_user.organization_id)
        .group_by(Sensor.status)
    )
    status_result = await db.execute(status_query)
    counts = {row[0]: row[1] for row in status_result.all()}

    # Average battery
    battery_query = (
        select(func.avg(Sensor.battery_level))
        .join(Asset)
        .where(Asset.organization_id == current_user.organization_id)
        .where(Sensor.battery_level.isnot(None))
    )
    avg_battery = (await db.execute(battery_query)).scalar() or 100.0

    total = sum(counts.values())

    return SensorStatusSummary(
        total_sensors=total,
        active=counts.get(SensorStatus.ACTIVE, 0),
        inactive=counts.get(SensorStatus.INACTIVE, 0),
        error=counts.get(SensorStatus.ERROR, 0),
        low_battery=counts.get(SensorStatus.LOW_BATTERY, 0),
        avg_battery_level=float(avg_battery)
    )


@router.get("/{sensor_id}", response_model=SensorResponse)
async def get_sensor(
    sensor_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get sensor details by ID."""
    result = await db.execute(
        select(Sensor)
        .join(Asset)
        .where(
            and_(
                Sensor.id == sensor_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    sensor = result.scalar_one_or_none()

    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")

    return sensor


@router.post("", response_model=SensorResponse, status_code=status.HTTP_201_CREATED)
async def create_sensor(
    sensor_data: SensorCreate,
    current_user: User = Depends(require_role(UserRole.TECHNICIAN)),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new sensor.

    Requires Technician role or higher.
    """
    # Verify asset belongs to organization
    asset_result = await db.execute(
        select(Asset).where(
            and_(
                Asset.id == sensor_data.asset_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    if not asset_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Asset not found")

    # Check for duplicate serial number
    existing = await db.execute(
        select(Sensor).where(Sensor.serial_number == sensor_data.serial_number)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Sensor with this serial number already exists"
        )

    sensor = Sensor(**sensor_data.model_dump())
    db.add(sensor)
    await db.commit()
    await db.refresh(sensor)

    return sensor


@router.put("/{sensor_id}", response_model=SensorResponse)
async def update_sensor(
    sensor_id: uuid.UUID,
    sensor_data: SensorUpdate,
    current_user: User = Depends(require_role(UserRole.TECHNICIAN)),
    db: AsyncSession = Depends(get_db)
):
    """Update sensor configuration."""
    result = await db.execute(
        select(Sensor)
        .join(Asset)
        .where(
            and_(
                Sensor.id == sensor_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    sensor = result.scalar_one_or_none()

    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")

    update_data = sensor_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(sensor, field, value)

    await db.commit()
    await db.refresh(sensor)

    return sensor


@router.delete("/{sensor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sensor(
    sensor_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Delete a sensor. Requires Admin role."""
    result = await db.execute(
        select(Sensor)
        .join(Asset)
        .where(
            and_(
                Sensor.id == sensor_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    sensor = result.scalar_one_or_none()

    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")

    await db.delete(sensor)
    await db.commit()


@router.post("/{sensor_id}/calibrate", response_model=SensorResponse)
async def calibrate_sensor(
    sensor_id: uuid.UUID,
    calibration: SensorCalibration,
    current_user: User = Depends(require_role(UserRole.TECHNICIAN)),
    db: AsyncSession = Depends(get_db)
):
    """Record sensor calibration."""
    result = await db.execute(
        select(Sensor)
        .join(Asset)
        .where(
            and_(
                Sensor.id == sensor_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    sensor = result.scalar_one_or_none()

    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")

    from datetime import timedelta, timezone
    now = datetime.now(timezone.utc)

    sensor.calibration_factor = calibration.calibration_factor
    sensor.calibration_offset = calibration.calibration_offset
    sensor.calibration_date = now
    sensor.calibration_due_date = now + timedelta(days=365)  # Default 1 year
    sensor.status = SensorStatus.ACTIVE

    await db.commit()
    await db.refresh(sensor)

    return sensor


@router.post("/{sensor_id}/activate", response_model=SensorResponse)
async def activate_sensor(
    sensor_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.TECHNICIAN)),
    db: AsyncSession = Depends(get_db)
):
    """Activate an inactive sensor."""
    result = await db.execute(
        select(Sensor)
        .join(Asset)
        .where(
            and_(
                Sensor.id == sensor_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    sensor = result.scalar_one_or_none()

    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")

    sensor.status = SensorStatus.ACTIVE
    await db.commit()
    await db.refresh(sensor)

    return sensor


@router.post("/{sensor_id}/deactivate", response_model=SensorResponse)
async def deactivate_sensor(
    sensor_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.TECHNICIAN)),
    db: AsyncSession = Depends(get_db)
):
    """Deactivate a sensor."""
    result = await db.execute(
        select(Sensor)
        .join(Asset)
        .where(
            and_(
                Sensor.id == sensor_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    sensor = result.scalar_one_or_none()

    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")

    sensor.status = SensorStatus.INACTIVE
    await db.commit()
    await db.refresh(sensor)

    return sensor
