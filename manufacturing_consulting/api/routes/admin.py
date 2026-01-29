"""
Admin dashboard API routes.

Provides system-wide monitoring and management for consultants.
"""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_

from api.dependencies import DatabaseDep, CurrentUserDep, require_system_role
from models.tenant import Tenant, TenantSubscription, UsageRecord, ServiceType
from models.quote_intelligence import Quote, QuoteStatus
from models.knowledge_preservation import SOP, Interview, SOPStatus, InterviewStatus
from models.erp_copilot import ERPQuery

router = APIRouter(dependencies=[Depends(require_system_role())])


@router.get("/dashboard")
async def get_dashboard_summary(
    db: DatabaseDep,
    current_user: CurrentUserDep,
):
    """Get admin dashboard summary."""
    # Total tenants
    tenants_result = await db.execute(
        select(func.count(Tenant.id)).where(Tenant.is_active == True)
    )
    total_tenants = tenants_result.scalar_one()
    
    # Active subscriptions by service
    subs_result = await db.execute(
        select(TenantSubscription.service_type, func.count(TenantSubscription.id))
        .where(TenantSubscription.status == "active")
        .group_by(TenantSubscription.service_type)
    )
    subscriptions_by_service = {
        row[0].value: row[1] for row in subs_result.all()
    }
    
    # Monthly recurring revenue (simplified)
    mrr_result = await db.execute(
        select(func.sum(TenantSubscription.monthly_price))
        .where(TenantSubscription.status == "active")
    )
    mrr = float(mrr_result.scalar_one() or 0)
    
    return {
        "total_tenants": total_tenants,
        "subscriptions_by_service": subscriptions_by_service,
        "monthly_recurring_revenue": mrr,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/activity")
async def get_recent_activity(
    db: DatabaseDep,
    current_user: CurrentUserDep,
    days: int = Query(7, ge=1, le=30),
):
    """Get recent system activity across all tenants."""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Quotes created
    quotes_result = await db.execute(
        select(func.count(Quote.id))
        .where(Quote.created_at >= start_date)
    )
    quotes_created = quotes_result.scalar_one()
    
    # SOPs generated
    sops_result = await db.execute(
        select(func.count(SOP.id))
        .where(
            and_(
                SOP.created_at >= start_date,
                SOP.ai_generated == True,
            )
        )
    )
    sops_generated = sops_result.scalar_one()
    
    # Interviews completed
    interviews_result = await db.execute(
        select(func.count(Interview.id))
        .where(
            and_(
                Interview.created_at >= start_date,
                Interview.status == InterviewStatus.PROCESSED,
            )
        )
    )
    interviews_completed = interviews_result.scalar_one()
    
    # ERP queries
    erp_queries_result = await db.execute(
        select(func.count(ERPQuery.id))
        .where(ERPQuery.created_at >= start_date)
    )
    erp_queries = erp_queries_result.scalar_one()
    
    return {
        "period_days": days,
        "quotes_created": quotes_created,
        "sops_generated": sops_generated,
        "interviews_completed": interviews_completed,
        "erp_queries": erp_queries,
    }


@router.get("/tenants/health")
async def get_tenant_health(
    db: DatabaseDep,
    current_user: CurrentUserDep,
):
    """Get health status for all active tenants."""
    # Get all active tenants
    tenants_result = await db.execute(
        select(Tenant).where(Tenant.is_active == True)
    )
    tenants = tenants_result.scalars().all()
    
    health_data = []
    last_7_days = datetime.utcnow() - timedelta(days=7)
    
    for tenant in tenants:
        # Get recent activity
        quotes = await db.execute(
            select(func.count(Quote.id))
            .where(
                and_(
                    Quote.tenant_id == tenant.id,
                    Quote.created_at >= last_7_days,
                )
            )
        )
        quote_count = quotes.scalar_one()
        
        erp = await db.execute(
            select(func.count(ERPQuery.id))
            .where(
                and_(
                    ERPQuery.tenant_id == tenant.id,
                    ERPQuery.created_at >= last_7_days,
                )
            )
        )
        erp_count = erp.scalar_one()
        
        # Determine health status
        activity_score = quote_count + erp_count
        if activity_score == 0:
            status = "inactive"
        elif activity_score < 10:
            status = "low_activity"
        else:
            status = "healthy"
        
        health_data.append({
            "tenant_id": tenant.id,
            "tenant_name": tenant.name,
            "status": status,
            "quotes_7d": quote_count,
            "erp_queries_7d": erp_count,
        })
    
    return {"items": health_data}


@router.get("/usage/summary")
async def get_usage_summary(
    db: DatabaseDep,
    current_user: CurrentUserDep,
    service_type: ServiceType | None = None,
    days: int = Query(30, ge=1, le=90),
):
    """Get usage summary across all tenants."""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    conditions = [UsageRecord.period_start >= start_date]
    if service_type:
        conditions.append(UsageRecord.service_type == service_type)
    
    result = await db.execute(
        select(
            UsageRecord.service_type,
            UsageRecord.metric_name,
            func.sum(UsageRecord.metric_value).label("total"),
        )
        .where(and_(*conditions))
        .group_by(UsageRecord.service_type, UsageRecord.metric_name)
    )
    
    usage_data = {}
    for row in result.all():
        service = row.service_type.value
        if service not in usage_data:
            usage_data[service] = {}
        usage_data[service][row.metric_name] = float(row.total)
    
    return {"period_days": days, "usage": usage_data}


@router.get("/quotes/pipeline")
async def get_quotes_pipeline(
    db: DatabaseDep,
    current_user: CurrentUserDep,
):
    """Get quote pipeline summary across all tenants."""
    result = await db.execute(
        select(Quote.status, func.count(Quote.id), func.sum(Quote.total_amount))
        .group_by(Quote.status)
    )
    
    pipeline = []
    for row in result.all():
        pipeline.append({
            "status": row[0].value,
            "count": row[1],
            "total_value": float(row[2] or 0),
        })
    
    return {"items": pipeline}


@router.get("/sops/status")
async def get_sops_status(
    db: DatabaseDep,
    current_user: CurrentUserDep,
):
    """Get SOP status summary across all tenants."""
    result = await db.execute(
        select(SOP.status, func.count(SOP.id))
        .group_by(SOP.status)
    )
    
    status_counts = {row[0].value: row[1] for row in result.all()}
    
    # AI generation stats
    ai_result = await db.execute(
        select(func.count(SOP.id), func.avg(SOP.ai_confidence_score))
        .where(SOP.ai_generated == True)
    )
    ai_stats = ai_result.one()
    
    return {
        "status_counts": status_counts,
        "ai_generated_count": ai_stats[0],
        "avg_ai_confidence": float(ai_stats[1] or 0),
    }


@router.get("/erp/performance")
async def get_erp_performance(
    db: DatabaseDep,
    current_user: CurrentUserDep,
    days: int = Query(7, ge=1, le=30),
):
    """Get ERP Copilot performance metrics across all tenants."""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    result = await db.execute(
        select(
            func.count(ERPQuery.id).label("total_queries"),
            func.avg(ERPQuery.response_time_ms).label("avg_response_time"),
            func.avg(ERPQuery.confidence_score).label("avg_confidence"),
            func.avg(ERPQuery.user_rating).label("avg_rating"),
            func.count(ERPQuery.id).filter(ERPQuery.was_fallback_used == True).label("fallback_count"),
        )
        .where(ERPQuery.created_at >= start_date)
    )
    
    row = result.one()
    
    return {
        "period_days": days,
        "total_queries": row.total_queries,
        "avg_response_time_ms": round(float(row.avg_response_time or 0), 2),
        "avg_confidence": round(float(row.avg_confidence or 0), 4),
        "avg_rating": round(float(row.avg_rating or 0), 2),
        "fallback_count": row.fallback_count,
        "success_rate": round((1 - (row.fallback_count / row.total_queries)) * 100, 2) if row.total_queries > 0 else 0,
    }


@router.get("/onboarding/pending")
async def get_pending_onboarding(
    db: DatabaseDep,
    current_user: CurrentUserDep,
):
    """Get tenants with incomplete onboarding."""
    result = await db.execute(
        select(Tenant)
        .where(
            and_(
                Tenant.is_active == True,
                Tenant.onboarding_completed == False,
            )
        )
        .order_by(Tenant.created_at)
    )
    tenants = result.scalars().all()
    
    return {
        "items": [
            {
                "id": t.id,
                "name": t.name,
                "created_at": t.created_at.isoformat(),
                "days_since_creation": (datetime.utcnow() - t.created_at).days,
            }
            for t in tenants
        ]
    }


@router.post("/tenants/{tenant_id}/onboarding/complete")
async def mark_onboarding_complete(
    tenant_id: str,
    db: DatabaseDep,
    current_user: CurrentUserDep,
):
    """Mark tenant onboarding as complete."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    tenant.onboarding_completed = True
    tenant.onboarding_completed_at = datetime.utcnow()
    
    await db.flush()
    
    return {"message": "Onboarding marked complete"}
