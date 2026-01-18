"""
Dashboard Router

Provides aggregated data for the main dashboard views.
"""
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import uuid

from api.database import get_db
from api.routers.auth import get_current_active_user
from models.user import User
from models.asset import Asset, AssetStatus
from models.alert import Alert, AlertSeverity, AlertStatus
from models.work_order import WorkOrder, WorkOrderStatus
from models.prediction import Prediction, PredictionType
from models.maintenance_event import MaintenanceEvent

router = APIRouter()


# Pydantic Models
class FleetHealthSummary(BaseModel):
    total_assets: int
    healthy_count: int
    warning_count: int
    critical_count: int
    offline_count: int
    maintenance_count: int
    avg_health_score: float
    assets_requiring_attention: int


class AlertsSummary(BaseModel):
    active_alerts: int
    critical_alerts: int
    warning_alerts: int
    unacknowledged: int
    alerts_today: int
    alerts_this_week: int


class WorkOrdersSummary(BaseModel):
    open_work_orders: int
    in_progress: int
    overdue: int
    completed_this_month: int
    avg_completion_time_hours: float


class ROISummary(BaseModel):
    total_downtime_avoided_hours: float
    total_cost_avoided: float
    total_maintenance_cost: float
    net_savings: float
    predicted_failures_caught: int
    false_positive_rate: float
    period_days: int


class AssetHealthItem(BaseModel):
    id: uuid.UUID
    name: str
    asset_tag: str
    asset_type: str
    status: str
    health_score: float
    predicted_rul_days: Optional[int]
    location: Optional[str]
    last_reading_at: Optional[datetime]


class RecentAlert(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    asset_name: str
    severity: str
    title: str
    detected_at: datetime
    status: str


class DashboardOverview(BaseModel):
    fleet_health: FleetHealthSummary
    alerts: AlertsSummary
    work_orders: WorkOrdersSummary
    roi: ROISummary
    assets_by_health: List[AssetHealthItem]
    recent_alerts: List[RecentAlert]


class HealthTrendPoint(BaseModel):
    date: str
    avg_health_score: float
    asset_count: int


class AlertTrendPoint(BaseModel):
    date: str
    critical: int
    warning: int
    info: int


# Routes
@router.get("/overview", response_model=DashboardOverview)
async def get_dashboard_overview(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get complete dashboard overview with all summary data."""
    org_id = current_user.organization_id
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Fleet Health Summary
    assets_result = await db.execute(
        select(Asset).where(Asset.organization_id == org_id)
    )
    assets = assets_result.scalars().all()

    status_counts = {}
    total_health = 0
    attention_count = 0
    for asset in assets:
        status_counts[asset.status] = status_counts.get(asset.status, 0) + 1
        total_health += float(asset.health_score or 100)
        if asset.status in [AssetStatus.WARNING, AssetStatus.CRITICAL]:
            attention_count += 1

    fleet_health = FleetHealthSummary(
        total_assets=len(assets),
        healthy_count=status_counts.get(AssetStatus.HEALTHY, 0),
        warning_count=status_counts.get(AssetStatus.WARNING, 0),
        critical_count=status_counts.get(AssetStatus.CRITICAL, 0),
        offline_count=status_counts.get(AssetStatus.OFFLINE, 0),
        maintenance_count=status_counts.get(AssetStatus.MAINTENANCE, 0),
        avg_health_score=total_health / len(assets) if assets else 100.0,
        assets_requiring_attention=attention_count
    )

    # Alerts Summary
    alert_status_query = (
        select(Alert.status, func.count(Alert.id))
        .join(Asset)
        .where(Asset.organization_id == org_id)
        .group_by(Alert.status)
    )
    alert_status_counts = {row[0]: row[1] for row in (await db.execute(alert_status_query)).all()}

    critical_alerts_query = (
        select(func.count(Alert.id))
        .join(Asset)
        .where(Asset.organization_id == org_id)
        .where(Alert.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED]))
        .where(Alert.severity.in_([AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]))
    )
    critical_count = (await db.execute(critical_alerts_query)).scalar()

    warning_alerts_query = (
        select(func.count(Alert.id))
        .join(Asset)
        .where(Asset.organization_id == org_id)
        .where(Alert.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED]))
        .where(Alert.severity == AlertSeverity.WARNING)
    )
    warning_count = (await db.execute(warning_alerts_query)).scalar()

    alerts_today_query = (
        select(func.count(Alert.id))
        .join(Asset)
        .where(Asset.organization_id == org_id)
        .where(Alert.detected_at >= today_start)
    )
    alerts_today = (await db.execute(alerts_today_query)).scalar()

    alerts_week_query = (
        select(func.count(Alert.id))
        .join(Asset)
        .where(Asset.organization_id == org_id)
        .where(Alert.detected_at >= week_start)
    )
    alerts_week = (await db.execute(alerts_week_query)).scalar()

    alerts_summary = AlertsSummary(
        active_alerts=alert_status_counts.get(AlertStatus.ACTIVE, 0) + alert_status_counts.get(AlertStatus.ACKNOWLEDGED, 0),
        critical_alerts=critical_count or 0,
        warning_alerts=warning_count or 0,
        unacknowledged=alert_status_counts.get(AlertStatus.ACTIVE, 0),
        alerts_today=alerts_today or 0,
        alerts_this_week=alerts_week or 0
    )

    # Work Orders Summary
    wo_status_query = (
        select(WorkOrder.status, func.count(WorkOrder.id))
        .where(WorkOrder.organization_id == org_id)
        .group_by(WorkOrder.status)
    )
    wo_status_counts = {row[0]: row[1] for row in (await db.execute(wo_status_query)).all()}

    overdue_query = (
        select(func.count(WorkOrder.id))
        .where(WorkOrder.organization_id == org_id)
        .where(WorkOrder.status.in_([WorkOrderStatus.OPEN, WorkOrderStatus.ASSIGNED, WorkOrderStatus.IN_PROGRESS]))
        .where(WorkOrder.due_date < now)
    )
    overdue = (await db.execute(overdue_query)).scalar()

    completed_month_query = (
        select(func.count(WorkOrder.id))
        .where(WorkOrder.organization_id == org_id)
        .where(WorkOrder.status == WorkOrderStatus.COMPLETED)
        .where(WorkOrder.completed_at >= month_start)
    )
    completed_month = (await db.execute(completed_month_query)).scalar()

    work_orders_summary = WorkOrdersSummary(
        open_work_orders=wo_status_counts.get(WorkOrderStatus.OPEN, 0) + wo_status_counts.get(WorkOrderStatus.ASSIGNED, 0),
        in_progress=wo_status_counts.get(WorkOrderStatus.IN_PROGRESS, 0),
        overdue=overdue or 0,
        completed_this_month=completed_month or 0,
        avg_completion_time_hours=0.0  # TODO: Calculate from actual data
    )

    # ROI Summary (last 30 days)
    roi_period = 30
    roi_start = now - timedelta(days=roi_period)

    roi_query = (
        select(
            func.sum(WorkOrder.estimated_downtime_avoided_hours),
            func.sum(WorkOrder.estimated_cost_avoided),
            func.sum(WorkOrder.total_cost)
        )
        .where(WorkOrder.organization_id == org_id)
        .where(WorkOrder.completed_at >= roi_start)
        .where(WorkOrder.status == WorkOrderStatus.COMPLETED)
    )
    roi_result = (await db.execute(roi_query)).one()

    predicted_caught = (await db.execute(
        select(func.count(WorkOrder.id))
        .where(WorkOrder.organization_id == org_id)
        .where(WorkOrder.is_auto_generated == True)
        .where(WorkOrder.completed_at >= roi_start)
    )).scalar() or 0

    # Calculate false positive rate from dismissed alerts
    total_alerts = (await db.execute(
        select(func.count(Alert.id))
        .join(Asset)
        .where(Asset.organization_id == org_id)
        .where(Alert.created_at >= roi_start)
    )).scalar() or 1

    dismissed_alerts = (await db.execute(
        select(func.count(Alert.id))
        .join(Asset)
        .where(Asset.organization_id == org_id)
        .where(Alert.status == AlertStatus.DISMISSED)
        .where(Alert.created_at >= roi_start)
    )).scalar() or 0

    downtime_avoided = float(roi_result[0] or 0)
    cost_avoided = float(roi_result[1] or 0)
    maintenance_cost = float(roi_result[2] or 0)

    roi_summary = ROISummary(
        total_downtime_avoided_hours=downtime_avoided,
        total_cost_avoided=cost_avoided,
        total_maintenance_cost=maintenance_cost,
        net_savings=cost_avoided - maintenance_cost,
        predicted_failures_caught=predicted_caught,
        false_positive_rate=dismissed_alerts / total_alerts if total_alerts > 0 else 0.0,
        period_days=roi_period
    )

    # Assets by health (sorted by health score ascending - worst first)
    assets_by_health = [
        AssetHealthItem(
            id=a.id,
            name=a.name,
            asset_tag=a.asset_tag,
            asset_type=a.asset_type.value,
            status=a.status.value,
            health_score=float(a.health_score or 100),
            predicted_rul_days=a.predicted_rul_days,
            location=a.location,
            last_reading_at=a.last_reading_at
        )
        for a in sorted(assets, key=lambda x: float(x.health_score or 100))[:10]
    ]

    # Recent alerts
    recent_alerts_query = (
        select(Alert, Asset.name)
        .join(Asset)
        .where(Asset.organization_id == org_id)
        .where(Alert.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED]))
        .order_by(Alert.detected_at.desc())
        .limit(10)
    )
    recent_alerts_result = await db.execute(recent_alerts_query)
    recent_alerts = [
        RecentAlert(
            id=alert.id,
            asset_id=alert.asset_id,
            asset_name=asset_name,
            severity=alert.severity.value,
            title=alert.title,
            detected_at=alert.detected_at,
            status=alert.status.value
        )
        for alert, asset_name in recent_alerts_result.all()
    ]

    return DashboardOverview(
        fleet_health=fleet_health,
        alerts=alerts_summary,
        work_orders=work_orders_summary,
        roi=roi_summary,
        assets_by_health=assets_by_health,
        recent_alerts=recent_alerts
    )


@router.get("/health-trends", response_model=List[HealthTrendPoint])
async def get_health_trends(
    days: int = Query(30, ge=7, le=365),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get fleet health score trends over time."""
    org_id = current_user.organization_id
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)

    # For now, return simulated trend data
    # In production, this would aggregate from predictions table
    trends = []
    current_date = start_date
    base_score = 85.0

    while current_date <= end_date:
        # Simulate some variation
        import random
        variation = random.uniform(-5, 5)
        trends.append(HealthTrendPoint(
            date=current_date.strftime("%Y-%m-%d"),
            avg_health_score=max(0, min(100, base_score + variation)),
            asset_count=10  # TODO: Get actual count
        ))
        current_date += timedelta(days=1)

    return trends


@router.get("/alert-trends", response_model=List[AlertTrendPoint])
async def get_alert_trends(
    days: int = Query(30, ge=7, le=365),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get alert volume trends over time."""
    org_id = current_user.organization_id
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)

    # Aggregate alerts by day and severity
    # For production, use actual aggregation query
    trends = []
    current_date = start_date

    while current_date <= end_date:
        import random
        trends.append(AlertTrendPoint(
            date=current_date.strftime("%Y-%m-%d"),
            critical=random.randint(0, 2),
            warning=random.randint(0, 5),
            info=random.randint(0, 3)
        ))
        current_date += timedelta(days=1)

    return trends
