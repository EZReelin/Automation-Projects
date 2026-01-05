"""
ERP Analytics service.

Provides usage analytics, gap identification, and reporting.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.erp_copilot import (
    ERPConfiguration, ERPQuery, ERPDocument, DocumentationGap,
    ERPUsageAnalytics, QueryCategory
)
from utils.logging import ServiceLogger


class ERPAnalyticsService:
    """
    Service for ERP Copilot analytics.
    
    Provides:
    - Usage metrics and reporting
    - Documentation gap analysis
    - User engagement tracking
    - Performance monitoring
    """
    
    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.logger = ServiceLogger("erp_analytics")
    
    async def get_usage_summary(
        self,
        days: int = 30,
    ) -> dict[str, Any]:
        """
        Get usage summary for the past N days.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with usage metrics
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Total queries
        total_result = await self.session.execute(
            select(func.count(ERPQuery.id)).where(
                and_(
                    ERPQuery.tenant_id == self.tenant_id,
                    ERPQuery.created_at >= start_date,
                )
            )
        )
        total_queries = total_result.scalar_one()
        
        # Unique users
        users_result = await self.session.execute(
            select(func.count(func.distinct(ERPQuery.user_id))).where(
                and_(
                    ERPQuery.tenant_id == self.tenant_id,
                    ERPQuery.created_at >= start_date,
                )
            )
        )
        unique_users = users_result.scalar_one()
        
        # Successful vs fallback queries
        fallback_result = await self.session.execute(
            select(
                func.count(ERPQuery.id).filter(ERPQuery.was_fallback_used == False),
                func.count(ERPQuery.id).filter(ERPQuery.was_fallback_used == True),
            ).where(
                and_(
                    ERPQuery.tenant_id == self.tenant_id,
                    ERPQuery.created_at >= start_date,
                )
            )
        )
        successful, fallback = fallback_result.one()
        
        # Average response time
        response_time_result = await self.session.execute(
            select(func.avg(ERPQuery.response_time_ms)).where(
                and_(
                    ERPQuery.tenant_id == self.tenant_id,
                    ERPQuery.created_at >= start_date,
                    ERPQuery.response_time_ms.isnot(None),
                )
            )
        )
        avg_response_time = response_time_result.scalar_one() or 0
        
        # Average rating
        rating_result = await self.session.execute(
            select(func.avg(ERPQuery.user_rating)).where(
                and_(
                    ERPQuery.tenant_id == self.tenant_id,
                    ERPQuery.created_at >= start_date,
                    ERPQuery.user_rating.isnot(None),
                )
            )
        )
        avg_rating = rating_result.scalar_one() or 0
        
        # Helpful percentage
        helpful_result = await self.session.execute(
            select(
                func.count(ERPQuery.id).filter(ERPQuery.was_helpful == True),
                func.count(ERPQuery.id).filter(ERPQuery.was_helpful.isnot(None)),
            ).where(
                and_(
                    ERPQuery.tenant_id == self.tenant_id,
                    ERPQuery.created_at >= start_date,
                )
            )
        )
        helpful_yes, helpful_total = helpful_result.one()
        helpful_pct = (helpful_yes / helpful_total * 100) if helpful_total > 0 else 0
        
        return {
            "period_days": days,
            "total_queries": total_queries,
            "unique_users": unique_users,
            "successful_queries": successful,
            "fallback_queries": fallback,
            "success_rate": (successful / total_queries * 100) if total_queries > 0 else 0,
            "avg_response_time_ms": round(avg_response_time, 2),
            "avg_rating": round(avg_rating, 2),
            "helpful_percentage": round(helpful_pct, 2),
        }
    
    async def get_queries_by_category(
        self,
        days: int = 30,
    ) -> list[dict]:
        """Get query breakdown by category."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.session.execute(
            select(
                ERPQuery.query_category,
                func.count(ERPQuery.id).label("count"),
            )
            .where(
                and_(
                    ERPQuery.tenant_id == self.tenant_id,
                    ERPQuery.created_at >= start_date,
                )
            )
            .group_by(ERPQuery.query_category)
            .order_by(func.count(ERPQuery.id).desc())
        )
        
        return [
            {
                "category": row.query_category.value if row.query_category else "other",
                "count": row.count,
            }
            for row in result.all()
        ]
    
    async def get_queries_by_module(
        self,
        days: int = 30,
    ) -> list[dict]:
        """Get query breakdown by ERP module."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.session.execute(
            select(
                ERPQuery.detected_entities["module"].astext.label("module"),
                func.count(ERPQuery.id).label("count"),
            )
            .where(
                and_(
                    ERPQuery.tenant_id == self.tenant_id,
                    ERPQuery.created_at >= start_date,
                    ERPQuery.detected_entities["module"].astext.isnot(None),
                )
            )
            .group_by(ERPQuery.detected_entities["module"].astext)
            .order_by(func.count(ERPQuery.id).desc())
        )
        
        return [
            {"module": row.module, "count": row.count}
            for row in result.all()
        ]
    
    async def get_daily_trend(
        self,
        days: int = 30,
    ) -> list[dict]:
        """Get daily query trend."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.session.execute(
            select(
                func.date(ERPQuery.created_at).label("date"),
                func.count(ERPQuery.id).label("total"),
                func.count(ERPQuery.id).filter(ERPQuery.was_fallback_used == False).label("successful"),
            )
            .where(
                and_(
                    ERPQuery.tenant_id == self.tenant_id,
                    ERPQuery.created_at >= start_date,
                )
            )
            .group_by(func.date(ERPQuery.created_at))
            .order_by(func.date(ERPQuery.created_at))
        )
        
        return [
            {
                "date": row.date.isoformat() if row.date else None,
                "total": row.total,
                "successful": row.successful,
            }
            for row in result.all()
        ]
    
    async def get_documentation_gaps(
        self,
        resolved: bool = False,
        severity: str | None = None,
        limit: int = 20,
    ) -> list[DocumentationGap]:
        """Get documentation gaps."""
        conditions = [
            DocumentationGap.tenant_id == self.tenant_id,
            DocumentationGap.is_resolved == resolved,
        ]
        
        if severity:
            conditions.append(DocumentationGap.severity == severity)
        
        result = await self.session.execute(
            select(DocumentationGap)
            .where(and_(*conditions))
            .order_by(DocumentationGap.query_count.desc())
            .limit(limit)
        )
        
        return list(result.scalars().all())
    
    async def resolve_gap(
        self,
        gap_id: str,
        resolution_document_id: str | None = None,
        resolution_notes: str | None = None,
    ) -> DocumentationGap | None:
        """Mark a documentation gap as resolved."""
        result = await self.session.execute(
            select(DocumentationGap).where(
                and_(
                    DocumentationGap.id == gap_id,
                    DocumentationGap.tenant_id == self.tenant_id,
                )
            )
        )
        gap = result.scalar_one_or_none()
        if not gap:
            return None
        
        gap.is_resolved = True
        gap.resolved_at = datetime.utcnow()
        gap.resolution_document_id = resolution_document_id
        gap.resolution_notes = resolution_notes
        
        await self.session.flush()
        return gap
    
    async def get_top_users(
        self,
        days: int = 30,
        limit: int = 10,
    ) -> list[dict]:
        """Get most active users."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.session.execute(
            select(
                ERPQuery.user_id,
                func.count(ERPQuery.id).label("query_count"),
                func.avg(ERPQuery.user_rating).label("avg_rating"),
            )
            .where(
                and_(
                    ERPQuery.tenant_id == self.tenant_id,
                    ERPQuery.created_at >= start_date,
                )
            )
            .group_by(ERPQuery.user_id)
            .order_by(func.count(ERPQuery.id).desc())
            .limit(limit)
        )
        
        return [
            {
                "user_id": row.user_id,
                "query_count": row.query_count,
                "avg_rating": round(float(row.avg_rating), 2) if row.avg_rating else None,
            }
            for row in result.all()
        ]
    
    async def get_performance_metrics(
        self,
        days: int = 7,
    ) -> dict[str, Any]:
        """Get system performance metrics."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.session.execute(
            select(
                func.avg(ERPQuery.response_time_ms).label("avg_response_time"),
                func.min(ERPQuery.response_time_ms).label("min_response_time"),
                func.max(ERPQuery.response_time_ms).label("max_response_time"),
                func.percentile_cont(0.5).within_group(ERPQuery.response_time_ms).label("median_response_time"),
                func.percentile_cont(0.95).within_group(ERPQuery.response_time_ms).label("p95_response_time"),
            ).where(
                and_(
                    ERPQuery.tenant_id == self.tenant_id,
                    ERPQuery.created_at >= start_date,
                    ERPQuery.response_time_ms.isnot(None),
                )
            )
        )
        
        row = result.one()
        
        return {
            "period_days": days,
            "avg_response_time_ms": round(float(row.avg_response_time or 0), 2),
            "min_response_time_ms": row.min_response_time,
            "max_response_time_ms": row.max_response_time,
            "median_response_time_ms": round(float(row.median_response_time or 0), 2),
            "p95_response_time_ms": round(float(row.p95_response_time or 0), 2),
        }
    
    async def generate_period_analytics(
        self,
        period_type: str,  # daily, weekly, monthly
        period_start: datetime,
        period_end: datetime,
    ) -> ERPUsageAnalytics:
        """
        Generate and store analytics for a period.
        
        Args:
            period_type: Type of period (daily, weekly, monthly)
            period_start: Start of period
            period_end: End of period
            
        Returns:
            ERPUsageAnalytics record
        """
        # Calculate metrics
        result = await self.session.execute(
            select(
                func.count(ERPQuery.id).label("total"),
                func.count(func.distinct(ERPQuery.user_id)).label("unique_users"),
                func.count(ERPQuery.id).filter(ERPQuery.was_fallback_used == False).label("successful"),
                func.count(ERPQuery.id).filter(ERPQuery.was_fallback_used == True).label("fallback"),
                func.avg(ERPQuery.response_time_ms).label("avg_response_time"),
                func.avg(ERPQuery.confidence_score).label("avg_confidence"),
                func.avg(ERPQuery.user_rating).label("avg_rating"),
                func.count(ERPQuery.id).filter(ERPQuery.was_helpful == True).label("positive_feedback"),
                func.count(ERPQuery.id).filter(ERPQuery.was_helpful == False).label("negative_feedback"),
            ).where(
                and_(
                    ERPQuery.tenant_id == self.tenant_id,
                    ERPQuery.created_at >= period_start,
                    ERPQuery.created_at < period_end,
                )
            )
        )
        metrics = result.one()
        
        # Get category breakdown
        category_result = await self.session.execute(
            select(
                ERPQuery.query_category,
                func.count(ERPQuery.id),
            )
            .where(
                and_(
                    ERPQuery.tenant_id == self.tenant_id,
                    ERPQuery.created_at >= period_start,
                    ERPQuery.created_at < period_end,
                )
            )
            .group_by(ERPQuery.query_category)
        )
        top_categories = {
            (row[0].value if row[0] else "other"): row[1]
            for row in category_result.all()
        }
        
        # Count gaps
        gaps_result = await self.session.execute(
            select(
                func.count(DocumentationGap.id).filter(
                    DocumentationGap.first_reported_at >= period_start
                ).label("new_gaps"),
                func.count(DocumentationGap.id).filter(
                    DocumentationGap.resolved_at >= period_start
                ).label("resolved_gaps"),
            ).where(DocumentationGap.tenant_id == self.tenant_id)
        )
        gaps = gaps_result.one()
        
        # Create analytics record
        from uuid import uuid4
        
        analytics = ERPUsageAnalytics(
            id=str(uuid4()),
            tenant_id=self.tenant_id,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            total_queries=metrics.total,
            unique_users=metrics.unique_users,
            successful_queries=metrics.successful,
            fallback_queries=metrics.fallback,
            avg_response_time_ms=float(metrics.avg_response_time or 0),
            avg_confidence_score=float(metrics.avg_confidence or 0),
            avg_rating=float(metrics.avg_rating or 0),
            positive_feedback_count=metrics.positive_feedback,
            negative_feedback_count=metrics.negative_feedback,
            top_categories=top_categories,
            new_gaps_identified=gaps.new_gaps,
            gaps_resolved=gaps.resolved_gaps,
        )
        
        self.session.add(analytics)
        await self.session.flush()
        
        return analytics
    
    async def get_historical_analytics(
        self,
        period_type: str,
        limit: int = 12,
    ) -> list[ERPUsageAnalytics]:
        """Get historical analytics records."""
        result = await self.session.execute(
            select(ERPUsageAnalytics)
            .where(
                and_(
                    ERPUsageAnalytics.tenant_id == self.tenant_id,
                    ERPUsageAnalytics.period_type == period_type,
                )
            )
            .order_by(ERPUsageAnalytics.period_start.desc())
            .limit(limit)
        )
        
        return list(result.scalars().all())
