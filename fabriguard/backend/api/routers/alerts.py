"""
Alerts Router

Manages alert listing, acknowledgment, and resolution.
"""
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
import uuid

from api.database import get_db
from api.routers.auth import get_current_active_user, require_role
from models.user import User, UserRole
from models.alert import Alert, AlertSeverity, AlertStatus, FailureMode
from models.asset import Asset

router = APIRouter()


# Pydantic Models
class AlertResponse(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    severity: AlertSeverity
    status: AlertStatus
    failure_mode: FailureMode
    title: str
    description: str
    recommendation: str
    confidence_score: float
    model_version: str
    trigger_reason: Optional[str]
    detected_at: datetime
    acknowledged_at: Optional[datetime]
    resolved_at: Optional[datetime]
    predicted_failure_date: Optional[datetime]
    action_deadline: Optional[datetime]
    work_order_id: Optional[uuid.UUID]
    created_at: datetime

    class Config:
        from_attributes = True


class AlertWithAsset(AlertResponse):
    asset_name: str
    asset_tag: str
    asset_location: Optional[str]


class AlertListResponse(BaseModel):
    items: List[AlertResponse]
    total: int
    page: int
    page_size: int
    unacknowledged_count: int


class AlertSummary(BaseModel):
    total_alerts: int
    active: int
    acknowledged: int
    in_progress: int
    resolved: int
    critical_count: int
    warning_count: int


class AlertAcknowledge(BaseModel):
    notes: Optional[str] = None


class AlertResolve(BaseModel):
    resolution_notes: str
    was_accurate: bool = True
    feedback_notes: Optional[str] = None


class AlertDismiss(BaseModel):
    reason: str
    feedback_notes: Optional[str] = None


# Routes
@router.get("", response_model=AlertListResponse)
async def list_alerts(
    asset_id: Optional[uuid.UUID] = None,
    severity: Optional[AlertSeverity] = None,
    status: Optional[AlertStatus] = None,
    failure_mode: Optional[FailureMode] = None,
    active_only: bool = True,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List alerts for the user's organization.

    By default, shows only active alerts (not resolved/dismissed).
    """
    query = (
        select(Alert)
        .join(Asset)
        .where(Asset.organization_id == current_user.organization_id)
    )

    if asset_id:
        query = query.where(Alert.asset_id == asset_id)
    if severity:
        query = query.where(Alert.severity == severity)
    if status:
        query = query.where(Alert.status == status)
    if failure_mode:
        query = query.where(Alert.failure_mode == failure_mode)
    if active_only:
        query = query.where(
            Alert.status.in_([
                AlertStatus.ACTIVE,
                AlertStatus.ACKNOWLEDGED,
                AlertStatus.IN_PROGRESS
            ])
        )

    # Get counts
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # Get unacknowledged count
    unack_query = (
        select(func.count(Alert.id))
        .join(Asset)
        .where(Asset.organization_id == current_user.organization_id)
        .where(Alert.status == AlertStatus.ACTIVE)
    )
    unacknowledged = (await db.execute(unack_query)).scalar()

    # Apply pagination and ordering
    query = (
        query
        .order_by(
            Alert.severity.desc(),
            Alert.detected_at.desc()
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    alerts = result.scalars().all()

    return AlertListResponse(
        items=alerts,
        total=total,
        page=page,
        page_size=page_size,
        unacknowledged_count=unacknowledged
    )


@router.get("/summary", response_model=AlertSummary)
async def get_alert_summary(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get aggregated alert summary."""
    org_id = current_user.organization_id

    # Status counts
    status_query = (
        select(Alert.status, func.count(Alert.id))
        .join(Asset)
        .where(Asset.organization_id == org_id)
        .group_by(Alert.status)
    )
    status_counts = {row[0]: row[1] for row in (await db.execute(status_query)).all()}

    # Severity counts for active alerts
    severity_query = (
        select(Alert.severity, func.count(Alert.id))
        .join(Asset)
        .where(Asset.organization_id == org_id)
        .where(Alert.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED, AlertStatus.IN_PROGRESS]))
        .group_by(Alert.severity)
    )
    severity_counts = {row[0]: row[1] for row in (await db.execute(severity_query)).all()}

    return AlertSummary(
        total_alerts=sum(status_counts.values()),
        active=status_counts.get(AlertStatus.ACTIVE, 0),
        acknowledged=status_counts.get(AlertStatus.ACKNOWLEDGED, 0),
        in_progress=status_counts.get(AlertStatus.IN_PROGRESS, 0),
        resolved=status_counts.get(AlertStatus.RESOLVED, 0) + status_counts.get(AlertStatus.AUTO_RESOLVED, 0),
        critical_count=severity_counts.get(AlertSeverity.CRITICAL, 0) + severity_counts.get(AlertSeverity.EMERGENCY, 0),
        warning_count=severity_counts.get(AlertSeverity.WARNING, 0)
    )


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get alert details."""
    result = await db.execute(
        select(Alert)
        .join(Asset)
        .where(
            and_(
                Alert.id == alert_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return alert


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: uuid.UUID,
    data: AlertAcknowledge,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Acknowledge an alert."""
    result = await db.execute(
        select(Alert)
        .join(Asset)
        .where(
            and_(
                Alert.id == alert_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if alert.status != AlertStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Alert is not in active status")

    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.acknowledged_by = current_user.id

    await db.commit()
    await db.refresh(alert)

    return alert


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: uuid.UUID,
    data: AlertResolve,
    current_user: User = Depends(require_role(UserRole.TECHNICIAN)),
    db: AsyncSession = Depends(get_db)
):
    """Resolve an alert."""
    result = await db.execute(
        select(Alert)
        .join(Asset)
        .where(
            and_(
                Alert.id == alert_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if alert.status in [AlertStatus.RESOLVED, AlertStatus.DISMISSED, AlertStatus.AUTO_RESOLVED]:
        raise HTTPException(status_code=400, detail="Alert is already resolved or dismissed")

    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = datetime.now(timezone.utc)
    alert.resolved_by = current_user.id
    alert.feedback_accurate = data.was_accurate
    alert.feedback_notes = data.feedback_notes
    alert.feedback_given_at = datetime.now(timezone.utc)
    alert.feedback_given_by = current_user.id

    await db.commit()
    await db.refresh(alert)

    return alert


@router.post("/{alert_id}/dismiss", response_model=AlertResponse)
async def dismiss_alert(
    alert_id: uuid.UUID,
    data: AlertDismiss,
    current_user: User = Depends(require_role(UserRole.TECHNICIAN)),
    db: AsyncSession = Depends(get_db)
):
    """Dismiss an alert (false positive)."""
    result = await db.execute(
        select(Alert)
        .join(Asset)
        .where(
            and_(
                Alert.id == alert_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = AlertStatus.DISMISSED
    alert.resolved_at = datetime.now(timezone.utc)
    alert.resolved_by = current_user.id
    alert.feedback_accurate = False
    alert.feedback_notes = f"Dismissed: {data.reason}. {data.feedback_notes or ''}"
    alert.feedback_given_at = datetime.now(timezone.utc)
    alert.feedback_given_by = current_user.id

    await db.commit()
    await db.refresh(alert)

    return alert


@router.post("/{alert_id}/create-work-order")
async def create_work_order_from_alert(
    alert_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.TECHNICIAN)),
    db: AsyncSession = Depends(get_db)
):
    """Create a work order from an alert."""
    from models.work_order import WorkOrder, WorkOrderStatus, WorkOrderPriority, WorkOrderType

    result = await db.execute(
        select(Alert)
        .join(Asset)
        .where(
            and_(
                Alert.id == alert_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if alert.work_order_id:
        raise HTTPException(status_code=400, detail="Work order already exists for this alert")

    # Map severity to priority
    priority_map = {
        AlertSeverity.EMERGENCY: WorkOrderPriority.EMERGENCY,
        AlertSeverity.CRITICAL: WorkOrderPriority.URGENT,
        AlertSeverity.WARNING: WorkOrderPriority.HIGH,
        AlertSeverity.INFO: WorkOrderPriority.MEDIUM
    }

    # Generate work order number
    import random
    wo_number = f"WO-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

    work_order = WorkOrder(
        asset_id=alert.asset_id,
        organization_id=current_user.organization_id,
        work_order_number=wo_number,
        title=f"Alert: {alert.title}",
        description=f"{alert.description}\n\nRecommendation: {alert.recommendation}",
        work_order_type=WorkOrderType.PREDICTIVE,
        status=WorkOrderStatus.OPEN,
        priority=priority_map.get(alert.severity, WorkOrderPriority.MEDIUM),
        source_alert_id=alert.id,
        is_auto_generated=True,
        due_date=alert.action_deadline
    )

    db.add(work_order)
    await db.flush()

    # Update alert
    alert.work_order_id = work_order.id
    alert.status = AlertStatus.IN_PROGRESS

    await db.commit()

    return {
        "message": "Work order created",
        "work_order_id": str(work_order.id),
        "work_order_number": work_order.work_order_number
    }
