"""
Work Orders Router

Manages maintenance work order lifecycle.
"""
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import uuid
import random

from api.database import get_db
from api.routers.auth import get_current_active_user, require_role
from models.user import User, UserRole
from models.work_order import WorkOrder, WorkOrderStatus, WorkOrderPriority, WorkOrderType
from models.asset import Asset

router = APIRouter()


# Pydantic Models
class WorkOrderCreate(BaseModel):
    asset_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=255)
    description: str
    work_order_type: WorkOrderType
    priority: WorkOrderPriority = WorkOrderPriority.MEDIUM
    due_date: Optional[datetime] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    procedures: Optional[str] = None
    safety_notes: Optional[str] = None
    tools_required: Optional[List[str]] = None
    parts_required: Optional[List[str]] = None
    estimated_hours: float = Field(default=0, ge=0)
    estimated_labor_cost: float = Field(default=0, ge=0)


class WorkOrderUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    priority: Optional[WorkOrderPriority] = None
    due_date: Optional[datetime] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    procedures: Optional[str] = None
    safety_notes: Optional[str] = None
    tools_required: Optional[List[str]] = None
    parts_required: Optional[List[str]] = None
    estimated_hours: Optional[float] = Field(None, ge=0)


class WorkOrderComplete(BaseModel):
    work_performed: str
    findings: Optional[str] = None
    root_cause: Optional[str] = None
    parts_used: Optional[List[str]] = None
    actual_hours: float = Field(..., ge=0)
    actual_labor_cost: float = Field(default=0, ge=0)
    parts_cost: float = Field(default=0, ge=0)
    external_service_cost: float = Field(default=0, ge=0)
    downtime_hours: float = Field(default=0, ge=0)
    downtime_avoided: bool = False
    estimated_downtime_avoided_hours: float = Field(default=0, ge=0)
    notes: Optional[str] = None


class WorkOrderResponse(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    organization_id: uuid.UUID
    work_order_number: str
    title: str
    description: str
    work_order_type: WorkOrderType
    status: WorkOrderStatus
    priority: WorkOrderPriority
    source_alert_id: Optional[uuid.UUID]
    is_auto_generated: bool
    assigned_to: Optional[uuid.UUID]
    assigned_at: Optional[datetime]
    due_date: Optional[datetime]
    scheduled_start: Optional[datetime]
    scheduled_end: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    procedures: Optional[str]
    safety_notes: Optional[str]
    tools_required: Optional[List[str]]
    parts_required: Optional[List[str]]
    work_performed: Optional[str]
    findings: Optional[str]
    estimated_hours: float
    actual_hours: float
    total_cost: float
    downtime_hours: float
    downtime_avoided: bool
    estimated_cost_avoided: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkOrderListResponse(BaseModel):
    items: List[WorkOrderResponse]
    total: int
    page: int
    page_size: int


class WorkOrderSummary(BaseModel):
    total: int
    open: int
    in_progress: int
    completed_this_month: int
    overdue: int
    total_cost_this_month: float
    total_downtime_avoided_hours: float
    total_cost_avoided: float


# Routes
@router.get("", response_model=WorkOrderListResponse)
async def list_work_orders(
    asset_id: Optional[uuid.UUID] = None,
    status: Optional[WorkOrderStatus] = None,
    priority: Optional[WorkOrderPriority] = None,
    work_order_type: Optional[WorkOrderType] = None,
    assigned_to: Optional[uuid.UUID] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List work orders for the organization."""
    query = select(WorkOrder).where(
        WorkOrder.organization_id == current_user.organization_id
    )

    if asset_id:
        query = query.where(WorkOrder.asset_id == asset_id)
    if status:
        query = query.where(WorkOrder.status == status)
    if priority:
        query = query.where(WorkOrder.priority == priority)
    if work_order_type:
        query = query.where(WorkOrder.work_order_type == work_order_type)
    if assigned_to:
        query = query.where(WorkOrder.assigned_to == assigned_to)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = (
        query
        .order_by(WorkOrder.priority.desc(), WorkOrder.due_date.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    work_orders = result.scalars().all()

    return WorkOrderListResponse(
        items=work_orders,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/summary", response_model=WorkOrderSummary)
async def get_work_order_summary(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get work order summary with ROI metrics."""
    org_id = current_user.organization_id
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Status counts
    status_query = (
        select(WorkOrder.status, func.count(WorkOrder.id))
        .where(WorkOrder.organization_id == org_id)
        .group_by(WorkOrder.status)
    )
    status_counts = {row[0]: row[1] for row in (await db.execute(status_query)).all()}

    # Completed this month
    completed_query = (
        select(func.count(WorkOrder.id))
        .where(WorkOrder.organization_id == org_id)
        .where(WorkOrder.status == WorkOrderStatus.COMPLETED)
        .where(WorkOrder.completed_at >= month_start)
    )
    completed_this_month = (await db.execute(completed_query)).scalar()

    # Overdue count
    overdue_query = (
        select(func.count(WorkOrder.id))
        .where(WorkOrder.organization_id == org_id)
        .where(WorkOrder.status.in_([WorkOrderStatus.OPEN, WorkOrderStatus.ASSIGNED, WorkOrderStatus.IN_PROGRESS]))
        .where(WorkOrder.due_date < now)
    )
    overdue = (await db.execute(overdue_query)).scalar()

    # Cost metrics this month
    cost_query = (
        select(
            func.sum(WorkOrder.total_cost),
            func.sum(WorkOrder.estimated_cost_avoided),
            func.sum(WorkOrder.estimated_downtime_avoided_hours)
        )
        .where(WorkOrder.organization_id == org_id)
        .where(WorkOrder.completed_at >= month_start)
    )
    cost_result = (await db.execute(cost_query)).one()

    return WorkOrderSummary(
        total=sum(status_counts.values()),
        open=status_counts.get(WorkOrderStatus.OPEN, 0) + status_counts.get(WorkOrderStatus.ASSIGNED, 0),
        in_progress=status_counts.get(WorkOrderStatus.IN_PROGRESS, 0),
        completed_this_month=completed_this_month or 0,
        overdue=overdue or 0,
        total_cost_this_month=float(cost_result[0] or 0),
        total_downtime_avoided_hours=float(cost_result[2] or 0),
        total_cost_avoided=float(cost_result[1] or 0)
    )


@router.get("/{work_order_id}", response_model=WorkOrderResponse)
async def get_work_order(
    work_order_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get work order details."""
    result = await db.execute(
        select(WorkOrder).where(
            and_(
                WorkOrder.id == work_order_id,
                WorkOrder.organization_id == current_user.organization_id
            )
        )
    )
    work_order = result.scalar_one_or_none()

    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    return work_order


@router.post("", response_model=WorkOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_work_order(
    data: WorkOrderCreate,
    current_user: User = Depends(require_role(UserRole.TECHNICIAN)),
    db: AsyncSession = Depends(get_db)
):
    """Create a new work order."""
    # Verify asset
    asset_result = await db.execute(
        select(Asset).where(
            and_(
                Asset.id == data.asset_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    if not asset_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Asset not found")

    wo_number = f"WO-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

    work_order = WorkOrder(
        organization_id=current_user.organization_id,
        work_order_number=wo_number,
        **data.model_dump()
    )

    db.add(work_order)
    await db.commit()
    await db.refresh(work_order)

    return work_order


@router.put("/{work_order_id}", response_model=WorkOrderResponse)
async def update_work_order(
    work_order_id: uuid.UUID,
    data: WorkOrderUpdate,
    current_user: User = Depends(require_role(UserRole.TECHNICIAN)),
    db: AsyncSession = Depends(get_db)
):
    """Update a work order."""
    result = await db.execute(
        select(WorkOrder).where(
            and_(
                WorkOrder.id == work_order_id,
                WorkOrder.organization_id == current_user.organization_id
            )
        )
    )
    work_order = result.scalar_one_or_none()

    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(work_order, field, value)

    await db.commit()
    await db.refresh(work_order)

    return work_order


@router.post("/{work_order_id}/assign", response_model=WorkOrderResponse)
async def assign_work_order(
    work_order_id: uuid.UUID,
    assignee_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    """Assign work order to a technician."""
    result = await db.execute(
        select(WorkOrder).where(
            and_(
                WorkOrder.id == work_order_id,
                WorkOrder.organization_id == current_user.organization_id
            )
        )
    )
    work_order = result.scalar_one_or_none()

    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    work_order.assigned_to = assignee_id
    work_order.assigned_by = current_user.id
    work_order.assigned_at = datetime.now(timezone.utc)
    work_order.status = WorkOrderStatus.ASSIGNED

    await db.commit()
    await db.refresh(work_order)

    return work_order


@router.post("/{work_order_id}/start", response_model=WorkOrderResponse)
async def start_work_order(
    work_order_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.TECHNICIAN)),
    db: AsyncSession = Depends(get_db)
):
    """Start working on a work order."""
    result = await db.execute(
        select(WorkOrder).where(
            and_(
                WorkOrder.id == work_order_id,
                WorkOrder.organization_id == current_user.organization_id
            )
        )
    )
    work_order = result.scalar_one_or_none()

    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    work_order.status = WorkOrderStatus.IN_PROGRESS
    work_order.started_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(work_order)

    return work_order


@router.post("/{work_order_id}/complete", response_model=WorkOrderResponse)
async def complete_work_order(
    work_order_id: uuid.UUID,
    data: WorkOrderComplete,
    current_user: User = Depends(require_role(UserRole.TECHNICIAN)),
    db: AsyncSession = Depends(get_db)
):
    """Complete a work order with results."""
    result = await db.execute(
        select(WorkOrder).where(
            and_(
                WorkOrder.id == work_order_id,
                WorkOrder.organization_id == current_user.organization_id
            )
        )
    )
    work_order = result.scalar_one_or_none()

    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    # Get asset for cost calculation
    asset_result = await db.execute(select(Asset).where(Asset.id == work_order.asset_id))
    asset = asset_result.scalar_one()

    work_order.status = WorkOrderStatus.COMPLETED
    work_order.completed_at = datetime.now(timezone.utc)
    work_order.completed_by = current_user.id
    work_order.work_performed = data.work_performed
    work_order.findings = data.findings
    work_order.root_cause = data.root_cause
    work_order.parts_used = data.parts_used
    work_order.actual_hours = data.actual_hours
    work_order.actual_labor_cost = data.actual_labor_cost
    work_order.parts_cost = data.parts_cost
    work_order.external_service_cost = data.external_service_cost
    work_order.total_cost = data.actual_labor_cost + data.parts_cost + data.external_service_cost
    work_order.downtime_hours = data.downtime_hours
    work_order.downtime_avoided = data.downtime_avoided
    work_order.estimated_downtime_avoided_hours = data.estimated_downtime_avoided_hours
    work_order.estimated_cost_avoided = data.estimated_downtime_avoided_hours * float(asset.hourly_downtime_cost)
    work_order.notes = data.notes

    await db.commit()
    await db.refresh(work_order)

    return work_order


@router.delete("/{work_order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_order(
    work_order_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Delete a work order. Requires Admin role."""
    result = await db.execute(
        select(WorkOrder).where(
            and_(
                WorkOrder.id == work_order_id,
                WorkOrder.organization_id == current_user.organization_id
            )
        )
    )
    work_order = result.scalar_one_or_none()

    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    await db.delete(work_order)
    await db.commit()
