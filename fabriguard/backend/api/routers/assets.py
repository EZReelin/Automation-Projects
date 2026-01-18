"""
Assets Router

Manages equipment/asset CRUD operations and health monitoring.
"""
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
import uuid

from api.database import get_db
from api.routers.auth import get_current_active_user, require_role
from models.user import User, UserRole
from models.asset import Asset, AssetType, AssetStatus

router = APIRouter()


# Pydantic Models
class AssetBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    asset_tag: str = Field(..., min_length=1, max_length=100)
    asset_type: AssetType
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    year_manufactured: Optional[int] = None
    installation_date: Optional[datetime] = None
    location: Optional[str] = None
    department: Optional[str] = None
    rated_capacity: Optional[str] = None
    criticality_score: int = Field(default=5, ge=1, le=10)
    hourly_downtime_cost: float = Field(default=5000.0, ge=0)
    maintenance_interval_days: int = Field(default=90, ge=1)
    notes: Optional[str] = None
    image_url: Optional[str] = None


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    asset_tag: Optional[str] = Field(None, min_length=1, max_length=100)
    asset_type: Optional[AssetType] = None
    status: Optional[AssetStatus] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    year_manufactured: Optional[int] = None
    installation_date: Optional[datetime] = None
    location: Optional[str] = None
    department: Optional[str] = None
    rated_capacity: Optional[str] = None
    criticality_score: Optional[int] = Field(None, ge=1, le=10)
    hourly_downtime_cost: Optional[float] = Field(None, ge=0)
    maintenance_interval_days: Optional[int] = Field(None, ge=1)
    notes: Optional[str] = None
    image_url: Optional[str] = None


class AssetResponse(AssetBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    status: AssetStatus
    health_score: float
    predicted_rul_days: Optional[int]
    confidence_score: Optional[float]
    last_reading_at: Optional[datetime]
    baseline_established: bool
    last_maintenance_date: Optional[datetime]
    next_scheduled_maintenance: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AssetListResponse(BaseModel):
    items: List[AssetResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AssetHealthSummary(BaseModel):
    total_assets: int
    healthy: int
    warning: int
    critical: int
    maintenance: int
    offline: int
    avg_health_score: float


# Routes
@router.get("", response_model=AssetListResponse)
async def list_assets(
    status: Optional[AssetStatus] = None,
    asset_type: Optional[AssetType] = None,
    location: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("name", regex="^(name|status|health_score|created_at)$"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all assets for the user's organization.

    Supports filtering by status, type, location, and search term.
    """
    # Build query
    query = select(Asset).where(Asset.organization_id == current_user.organization_id)

    # Apply filters
    if status:
        query = query.where(Asset.status == status)
    if asset_type:
        query = query.where(Asset.asset_type == asset_type)
    if location:
        query = query.where(Asset.location.ilike(f"%{location}%"))
    if search:
        query = query.where(
            Asset.name.ilike(f"%{search}%") |
            Asset.asset_tag.ilike(f"%{search}%") |
            Asset.serial_number.ilike(f"%{search}%")
        )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # Apply sorting
    sort_column = getattr(Asset, sort_by)
    if sort_order == "desc":
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)

    # Execute
    result = await db.execute(query)
    assets = result.scalars().all()

    return AssetListResponse(
        items=assets,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )


@router.get("/health-summary", response_model=AssetHealthSummary)
async def get_health_summary(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get aggregated health summary for all assets."""
    org_id = current_user.organization_id

    # Count by status
    status_counts = await db.execute(
        select(Asset.status, func.count(Asset.id))
        .where(Asset.organization_id == org_id)
        .group_by(Asset.status)
    )
    counts = {row[0]: row[1] for row in status_counts.all()}

    # Average health score
    avg_query = await db.execute(
        select(func.avg(Asset.health_score))
        .where(Asset.organization_id == org_id)
    )
    avg_health = avg_query.scalar() or 100.0

    total = sum(counts.values())

    return AssetHealthSummary(
        total_assets=total,
        healthy=counts.get(AssetStatus.HEALTHY, 0),
        warning=counts.get(AssetStatus.WARNING, 0),
        critical=counts.get(AssetStatus.CRITICAL, 0),
        maintenance=counts.get(AssetStatus.MAINTENANCE, 0),
        offline=counts.get(AssetStatus.OFFLINE, 0),
        avg_health_score=float(avg_health)
    )


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get asset details by ID."""
    result = await db.execute(
        select(Asset)
        .where(
            and_(
                Asset.id == asset_id,
                Asset.organization_id == current_user.organization_id
            )
        )
        .options(selectinload(Asset.sensors))
    )
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )

    return asset


@router.post("", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    asset_data: AssetCreate,
    current_user: User = Depends(require_role(UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new asset.

    Requires Manager role or higher.
    """
    # Check for duplicate asset_tag
    existing = await db.execute(
        select(Asset).where(
            and_(
                Asset.organization_id == current_user.organization_id,
                Asset.asset_tag == asset_data.asset_tag
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Asset tag already exists"
        )

    asset = Asset(
        organization_id=current_user.organization_id,
        **asset_data.model_dump()
    )

    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    return asset


@router.put("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: uuid.UUID,
    asset_data: AssetUpdate,
    current_user: User = Depends(require_role(UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    """
    Update an existing asset.

    Requires Manager role or higher.
    """
    result = await db.execute(
        select(Asset).where(
            and_(
                Asset.id == asset_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )

    # Update fields
    update_data = asset_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(asset, field, value)

    await db.commit()
    await db.refresh(asset)

    return asset


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete an asset.

    Requires Admin role or higher. This will also delete all
    associated sensors, readings, alerts, and work orders.
    """
    result = await db.execute(
        select(Asset).where(
            and_(
                Asset.id == asset_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )

    await db.delete(asset)
    await db.commit()


@router.post("/{asset_id}/set-maintenance", response_model=AssetResponse)
async def set_maintenance_mode(
    asset_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.TECHNICIAN)),
    db: AsyncSession = Depends(get_db)
):
    """Put asset into maintenance mode."""
    result = await db.execute(
        select(Asset).where(
            and_(
                Asset.id == asset_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    asset.status = AssetStatus.MAINTENANCE
    asset.last_maintenance_date = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(asset)

    return asset


@router.post("/{asset_id}/complete-maintenance", response_model=AssetResponse)
async def complete_maintenance(
    asset_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.TECHNICIAN)),
    db: AsyncSession = Depends(get_db)
):
    """Mark maintenance as complete and restore asset to monitoring."""
    result = await db.execute(
        select(Asset).where(
            and_(
                Asset.id == asset_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    asset = result.scalar_one_or_none()

    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    asset.status = AssetStatus.HEALTHY
    asset.health_score = 100.0
    asset.predicted_rul_days = None

    # Calculate next maintenance date
    from datetime import timedelta
    asset.next_scheduled_maintenance = (
        datetime.now(timezone.utc) + timedelta(days=asset.maintenance_interval_days)
    )

    await db.commit()
    await db.refresh(asset)

    return asset
