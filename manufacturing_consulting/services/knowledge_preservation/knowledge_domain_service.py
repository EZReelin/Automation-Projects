"""
Knowledge domain management service.

Manages knowledge areas and tracks preservation progress.
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.knowledge_preservation import (
    KnowledgeDomain, KnowledgeDomainCategory, SubjectMatterExpert,
    Interview, SOP, InterviewStatus, SOPStatus
)
from utils.logging import ServiceLogger


class KnowledgeDomainService:
    """
    Service for managing knowledge domains.
    
    Provides:
    - Domain CRUD operations
    - SME (Subject Matter Expert) management
    - Progress tracking
    - Knowledge gap analysis
    """
    
    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.logger = ServiceLogger("knowledge_domain")
    
    async def create_domain(
        self,
        name: str,
        code: str,
        category: KnowledgeDomainCategory = KnowledgeDomainCategory.OTHER,
        description: str | None = None,
        **kwargs: Any,
    ) -> KnowledgeDomain:
        """
        Create a new knowledge domain.
        
        Args:
            name: Domain name
            code: Unique code identifier
            category: Domain category
            description: Domain description
            **kwargs: Additional attributes
            
        Returns:
            Created KnowledgeDomain instance
        """
        domain = KnowledgeDomain(
            id=str(uuid4()),
            tenant_id=self.tenant_id,
            name=name,
            code=code,
            category=category,
            description=description,
            **kwargs,
        )
        
        self.session.add(domain)
        await self.session.flush()
        
        return domain
    
    async def get_domain(self, domain_id: str) -> KnowledgeDomain | None:
        """Get a knowledge domain by ID."""
        result = await self.session.execute(
            select(KnowledgeDomain).where(
                and_(
                    KnowledgeDomain.id == domain_id,
                    KnowledgeDomain.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def list_domains(
        self,
        category: KnowledgeDomainCategory | None = None,
        is_active: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[KnowledgeDomain], int]:
        """List knowledge domains with filters."""
        conditions = [
            KnowledgeDomain.tenant_id == self.tenant_id,
            KnowledgeDomain.is_active == is_active,
        ]
        
        if category:
            conditions.append(KnowledgeDomain.category == category)
        
        # Count
        count_result = await self.session.execute(
            select(func.count(KnowledgeDomain.id)).where(and_(*conditions))
        )
        total = count_result.scalar_one()
        
        # Get domains
        result = await self.session.execute(
            select(KnowledgeDomain)
            .where(and_(*conditions))
            .order_by(KnowledgeDomain.name)
            .limit(limit)
            .offset(offset)
        )
        domains = result.scalars().all()
        
        return list(domains), total
    
    async def update_domain(
        self,
        domain_id: str,
        **updates: Any,
    ) -> KnowledgeDomain | None:
        """Update a knowledge domain."""
        domain = await self.get_domain(domain_id)
        if not domain:
            return None
        
        for key, value in updates.items():
            if hasattr(domain, key) and key not in ["id", "tenant_id"]:
                setattr(domain, key, value)
        
        domain.updated_at = datetime.utcnow()
        await self.session.flush()
        
        return domain
    
    async def get_domain_progress(self, domain_id: str) -> dict:
        """
        Get progress metrics for a knowledge domain.
        
        Returns:
            Dictionary with progress metrics
        """
        # Count interviews
        interviews_result = await self.session.execute(
            select(
                func.count(Interview.id).label("total"),
                func.count(Interview.id).filter(
                    Interview.status == InterviewStatus.PROCESSED
                ).label("completed"),
            )
            .where(
                and_(
                    Interview.knowledge_domain_id == domain_id,
                    Interview.tenant_id == self.tenant_id,
                )
            )
        )
        interviews = interviews_result.one()
        
        # Count SOPs
        sops_result = await self.session.execute(
            select(
                func.count(SOP.id).label("total"),
                func.count(SOP.id).filter(
                    SOP.status == SOPStatus.PUBLISHED
                ).label("published"),
                func.count(SOP.id).filter(
                    SOP.status == SOPStatus.APPROVED
                ).label("approved"),
            )
            .where(
                and_(
                    SOP.knowledge_domain_id == domain_id,
                    SOP.tenant_id == self.tenant_id,
                )
            )
        )
        sops = sops_result.one()
        
        # Calculate completion percentage
        total_items = interviews.total + sops.total
        completed_items = interviews.completed + sops.published + sops.approved
        completion_pct = int((completed_items / total_items * 100)) if total_items > 0 else 0
        
        # Update domain
        domain = await self.get_domain(domain_id)
        if domain:
            domain.completion_percentage = completion_pct
            await self.session.flush()
        
        return {
            "interviews": {
                "total": interviews.total,
                "completed": interviews.completed,
            },
            "sops": {
                "total": sops.total,
                "published": sops.published,
                "approved": sops.approved,
            },
            "completion_percentage": completion_pct,
        }
    
    # Subject Matter Expert Management
    
    async def create_sme(
        self,
        first_name: str,
        last_name: str,
        department: str | None = None,
        job_title: str | None = None,
        email: str | None = None,
        **kwargs: Any,
    ) -> SubjectMatterExpert:
        """Create a subject matter expert record."""
        sme = SubjectMatterExpert(
            id=str(uuid4()),
            tenant_id=self.tenant_id,
            first_name=first_name,
            last_name=last_name,
            department=department,
            job_title=job_title,
            email=email,
            **kwargs,
        )
        
        self.session.add(sme)
        await self.session.flush()
        
        return sme
    
    async def get_sme(self, sme_id: str) -> SubjectMatterExpert | None:
        """Get a subject matter expert by ID."""
        result = await self.session.execute(
            select(SubjectMatterExpert).where(
                and_(
                    SubjectMatterExpert.id == sme_id,
                    SubjectMatterExpert.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def list_smes(
        self,
        is_retiring: bool | None = None,
        department: str | None = None,
        is_active: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SubjectMatterExpert], int]:
        """List subject matter experts with filters."""
        conditions = [
            SubjectMatterExpert.tenant_id == self.tenant_id,
            SubjectMatterExpert.is_active == is_active,
        ]
        
        if is_retiring is not None:
            conditions.append(SubjectMatterExpert.is_retiring == is_retiring)
        
        if department:
            conditions.append(SubjectMatterExpert.department == department)
        
        # Count
        count_result = await self.session.execute(
            select(func.count(SubjectMatterExpert.id)).where(and_(*conditions))
        )
        total = count_result.scalar_one()
        
        # Get SMEs
        result = await self.session.execute(
            select(SubjectMatterExpert)
            .where(and_(*conditions))
            .order_by(SubjectMatterExpert.last_name)
            .limit(limit)
            .offset(offset)
        )
        smes = result.scalars().all()
        
        return list(smes), total
    
    async def get_retiring_smes_priority(self) -> list[dict]:
        """
        Get retiring SMEs sorted by knowledge capture priority.
        
        Returns:
            List of SMEs with their priority scores
        """
        result = await self.session.execute(
            select(SubjectMatterExpert)
            .where(
                and_(
                    SubjectMatterExpert.tenant_id == self.tenant_id,
                    SubjectMatterExpert.is_retiring == True,
                    SubjectMatterExpert.is_active == True,
                )
            )
            .order_by(SubjectMatterExpert.expected_departure_date)
        )
        smes = result.scalars().all()
        
        prioritized = []
        for sme in smes:
            # Calculate priority score
            days_until_departure = 365  # Default
            if sme.expected_departure_date:
                delta = sme.expected_departure_date - datetime.utcnow()
                days_until_departure = max(0, delta.days)
            
            # Get interview count
            interview_count = await self._count_sme_interviews(sme.id)
            
            priority_score = 100 - min(100, days_until_departure / 3)  # Higher urgency for sooner departures
            priority_score += (sme.years_of_experience or 0) * 2  # More experience = higher priority
            priority_score -= interview_count * 5  # Already captured knowledge lowers priority
            
            prioritized.append({
                "sme": sme,
                "days_until_departure": days_until_departure,
                "interviews_completed": interview_count,
                "priority_score": max(0, priority_score),
            })
        
        return sorted(prioritized, key=lambda x: x["priority_score"], reverse=True)
    
    async def _count_sme_interviews(self, sme_id: str) -> int:
        """Count completed interviews for an SME."""
        result = await self.session.execute(
            select(func.count(Interview.id)).where(
                and_(
                    Interview.sme_id == sme_id,
                    Interview.tenant_id == self.tenant_id,
                    Interview.status == InterviewStatus.PROCESSED,
                )
            )
        )
        return result.scalar_one()
    
    async def get_knowledge_gaps(self) -> list[dict]:
        """
        Identify knowledge gaps in the organization.
        
        Returns:
            List of domains with low coverage or at-risk knowledge
        """
        domains, _ = await self.list_domains()
        
        gaps = []
        for domain in domains:
            progress = await self.get_domain_progress(domain.id)
            
            # Check for gaps
            has_gap = False
            gap_reasons = []
            
            if progress["completion_percentage"] < 50:
                has_gap = True
                gap_reasons.append(f"Low completion: {progress['completion_percentage']}%")
            
            if progress["interviews"]["total"] == 0:
                has_gap = True
                gap_reasons.append("No interviews scheduled")
            
            if progress["sops"]["published"] == 0 and domain.completion_percentage > 0:
                has_gap = True
                gap_reasons.append("No published SOPs")
            
            if has_gap:
                gaps.append({
                    "domain": domain,
                    "progress": progress,
                    "gap_reasons": gap_reasons,
                })
        
        return gaps
