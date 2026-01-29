"""
SOP (Standard Operating Procedure) generation and management service.

Converts interview content to structured SOPs with review workflows.
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.knowledge_preservation import (
    SOP, SOPTemplate, SOPVersion, SOPReviewComment, SOPAttachment,
    Interview, KnowledgeDomain, SOPStatus, SOPPriority
)
from utils.logging import ServiceLogger
from utils.ai_client import ai_client
from config.settings import settings


class SOPService:
    """
    Service for managing Standard Operating Procedures.
    
    Provides:
    - SOP generation from interviews
    - Template-based SOP creation
    - Review and approval workflows
    - Version control
    - Search and retrieval
    """
    
    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.logger = ServiceLogger("sop")
    
    async def generate_sop_from_interview(
        self,
        interview_id: str,
        template_id: str | None = None,
        created_by_id: str | None = None,
    ) -> SOP:
        """
        Generate an SOP from a processed interview.
        
        Args:
            interview_id: Source interview ID
            template_id: Optional SOP template to use
            created_by_id: Creating user ID
            
        Returns:
            Generated SOP instance
        """
        self.logger.log_operation_start(
            "generate_sop_from_interview",
            tenant_id=self.tenant_id,
            interview_id=interview_id,
        )
        
        # Get interview
        interview = await self._get_interview(interview_id)
        if not interview:
            raise ValueError(f"Interview not found: {interview_id}")
        
        if not interview.transcript_cleaned:
            raise ValueError("Interview has not been processed")
        
        # Get template
        template = None
        if template_id:
            template = await self._get_template(template_id)
        else:
            # Try to find default template for domain category
            domain = await self._get_knowledge_domain(interview.knowledge_domain_id)
            if domain:
                template = await self._find_default_template(domain.category)
        
        # Generate SOP content
        content = await self._generate_sop_content(interview, template)
        
        # Generate SOP number
        sop_number = await self._generate_sop_number()
        
        # Create SOP
        sop = SOP(
            id=str(uuid4()),
            tenant_id=self.tenant_id,
            sop_number=sop_number,
            title=interview.title,
            knowledge_domain_id=interview.knowledge_domain_id,
            source_interview_id=interview_id,
            template_id=template_id,
            status=SOPStatus.DRAFT,
            content=content,
            content_plain_text=self._content_to_plain_text(content),
            ai_generated=True,
            ai_confidence_score=content.get("confidence_score", 0.75),
            ai_model_used=settings.ai.default_model,
            created_by_id=created_by_id,
            effective_date=datetime.utcnow() + timedelta(days=14),  # 2 weeks for review
            next_review_date=datetime.utcnow() + timedelta(days=365),  # Annual review
            tags=interview.extracted_topics or [],
        )
        
        self.session.add(sop)
        await self.session.flush()
        
        # Create initial version
        await self._create_version(sop, "AI-generated from interview", created_by_id)
        
        self.logger.log_operation_complete(
            "generate_sop_from_interview",
            tenant_id=self.tenant_id,
            sop_id=sop.id,
        )
        
        return sop
    
    async def create_sop(
        self,
        title: str,
        knowledge_domain_id: str,
        content: dict,
        template_id: str | None = None,
        created_by_id: str | None = None,
        **kwargs: Any,
    ) -> SOP:
        """
        Create a new SOP manually.
        
        Args:
            title: SOP title
            knowledge_domain_id: Related knowledge domain
            content: SOP content dictionary
            template_id: Template used
            created_by_id: Creating user ID
            **kwargs: Additional attributes
            
        Returns:
            Created SOP instance
        """
        sop_number = await self._generate_sop_number()
        
        sop = SOP(
            id=str(uuid4()),
            tenant_id=self.tenant_id,
            sop_number=sop_number,
            title=title,
            knowledge_domain_id=knowledge_domain_id,
            template_id=template_id,
            status=SOPStatus.DRAFT,
            content=content,
            content_plain_text=self._content_to_plain_text(content),
            ai_generated=False,
            created_by_id=created_by_id,
            next_review_date=datetime.utcnow() + timedelta(days=365),
            **kwargs,
        )
        
        self.session.add(sop)
        await self.session.flush()
        
        await self._create_version(sop, "Initial creation", created_by_id)
        
        return sop
    
    async def get_sop(self, sop_id: str) -> SOP | None:
        """Get an SOP by ID."""
        result = await self.session.execute(
            select(SOP)
            .where(
                and_(
                    SOP.id == sop_id,
                    SOP.tenant_id == self.tenant_id,
                )
            )
            .options(
                selectinload(SOP.review_comments),
                selectinload(SOP.attachments),
            )
        )
        return result.scalar_one_or_none()
    
    async def update_sop(
        self,
        sop_id: str,
        updated_by_id: str,
        change_summary: str | None = None,
        **updates: Any,
    ) -> SOP | None:
        """
        Update an SOP and create a new version.
        
        Args:
            sop_id: SOP to update
            updated_by_id: User making the update
            change_summary: Description of changes
            **updates: Fields to update
            
        Returns:
            Updated SOP or None
        """
        sop = await self.get_sop(sop_id)
        if not sop:
            return None
        
        # Track if content changed for versioning
        content_changed = "content" in updates
        
        for key, value in updates.items():
            if hasattr(sop, key) and key not in ["id", "tenant_id", "sop_number"]:
                setattr(sop, key, value)
        
        if content_changed:
            sop.content_plain_text = self._content_to_plain_text(sop.content)
        
        sop.updated_at = datetime.utcnow()
        
        # Create version for significant changes
        if content_changed:
            # Increment version
            current_version = sop.version
            parts = current_version.split(".")
            parts[-1] = str(int(parts[-1]) + 1)
            sop.version = ".".join(parts)
            
            await self._create_version(
                sop,
                change_summary or "Content updated",
                updated_by_id,
            )
        
        await self.session.flush()
        return sop
    
    async def submit_for_review(
        self,
        sop_id: str,
        submitted_by_id: str,
        reviewer_id: str | None = None,
    ) -> SOP | None:
        """Submit an SOP for review."""
        sop = await self.get_sop(sop_id)
        if not sop or sop.status != SOPStatus.DRAFT:
            return None
        
        sop.status = SOPStatus.PENDING_REVIEW
        sop.current_reviewer_id = reviewer_id
        sop.updated_at = datetime.utcnow()
        
        await self.session.flush()
        return sop
    
    async def start_review(
        self,
        sop_id: str,
        reviewer_id: str,
    ) -> SOP | None:
        """Mark an SOP as being actively reviewed."""
        sop = await self.get_sop(sop_id)
        if not sop or sop.status != SOPStatus.PENDING_REVIEW:
            return None
        
        sop.status = SOPStatus.IN_REVIEW
        sop.current_reviewer_id = reviewer_id
        sop.review_date = datetime.utcnow()
        sop.updated_at = datetime.utcnow()
        
        await self.session.flush()
        return sop
    
    async def add_review_comment(
        self,
        sop_id: str,
        author_id: str,
        comment_text: str,
        section_reference: str | None = None,
        requires_action: bool = False,
        parent_comment_id: str | None = None,
    ) -> SOPReviewComment:
        """Add a review comment to an SOP."""
        comment = SOPReviewComment(
            id=str(uuid4()),
            tenant_id=self.tenant_id,
            sop_id=sop_id,
            author_id=author_id,
            comment_text=comment_text,
            section_reference=section_reference,
            requires_action=requires_action,
            parent_comment_id=parent_comment_id,
            comment_type="review" if requires_action else "general",
        )
        
        self.session.add(comment)
        await self.session.flush()
        
        return comment
    
    async def resolve_comment(
        self,
        comment_id: str,
        resolved_by_id: str,
        resolution_note: str | None = None,
    ) -> SOPReviewComment | None:
        """Resolve a review comment."""
        result = await self.session.execute(
            select(SOPReviewComment).where(
                and_(
                    SOPReviewComment.id == comment_id,
                    SOPReviewComment.tenant_id == self.tenant_id,
                )
            )
        )
        comment = result.scalar_one_or_none()
        if not comment:
            return None
        
        comment.is_resolved = True
        comment.resolved_by_id = resolved_by_id
        comment.resolved_at = datetime.utcnow()
        comment.resolution_note = resolution_note
        
        await self.session.flush()
        return comment
    
    async def request_revision(
        self,
        sop_id: str,
        reviewer_id: str,
        reason: str,
    ) -> SOP | None:
        """Request revisions for an SOP."""
        sop = await self.get_sop(sop_id)
        if not sop:
            return None
        
        sop.status = SOPStatus.REVISION_REQUESTED
        sop.updated_at = datetime.utcnow()
        
        # Add revision comment
        await self.add_review_comment(
            sop_id=sop_id,
            author_id=reviewer_id,
            comment_text=reason,
            requires_action=True,
            comment_type="revision",
        )
        
        await self.session.flush()
        return sop
    
    async def approve_sop(
        self,
        sop_id: str,
        approved_by_id: str,
    ) -> SOP | None:
        """Approve an SOP."""
        sop = await self.get_sop(sop_id)
        if not sop or sop.status not in [SOPStatus.IN_REVIEW, SOPStatus.PENDING_REVIEW]:
            return None
        
        # Check for unresolved required comments
        unresolved = await self._count_unresolved_comments(sop_id)
        if unresolved > 0:
            raise ValueError(f"Cannot approve: {unresolved} unresolved comments")
        
        sop.status = SOPStatus.APPROVED
        sop.approved_by_id = approved_by_id
        sop.approved_at = datetime.utcnow()
        sop.updated_at = datetime.utcnow()
        
        await self._create_version(sop, "Approved", approved_by_id, change_type="major")
        
        await self.session.flush()
        return sop
    
    async def publish_sop(
        self,
        sop_id: str,
        published_by_id: str,
        effective_date: datetime | None = None,
    ) -> SOP | None:
        """Publish an approved SOP."""
        sop = await self.get_sop(sop_id)
        if not sop or sop.status != SOPStatus.APPROVED:
            return None
        
        sop.status = SOPStatus.PUBLISHED
        sop.effective_date = effective_date or datetime.utcnow()
        sop.updated_at = datetime.utcnow()
        
        await self.session.flush()
        return sop
    
    async def search_sops(
        self,
        query: str | None = None,
        knowledge_domain_id: str | None = None,
        status: SOPStatus | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SOP], int]:
        """Search SOPs with filters."""
        from sqlalchemy import or_
        
        conditions = [SOP.tenant_id == self.tenant_id]
        
        if query:
            search_pattern = f"%{query}%"
            conditions.append(
                or_(
                    SOP.title.ilike(search_pattern),
                    SOP.sop_number.ilike(search_pattern),
                    SOP.content_plain_text.ilike(search_pattern),
                )
            )
        
        if knowledge_domain_id:
            conditions.append(SOP.knowledge_domain_id == knowledge_domain_id)
        
        if status:
            conditions.append(SOP.status == status)
        
        if tags:
            conditions.append(SOP.tags.overlap(tags))
        
        # Count
        count_result = await self.session.execute(
            select(func.count(SOP.id)).where(and_(*conditions))
        )
        total = count_result.scalar_one()
        
        # Get SOPs
        result = await self.session.execute(
            select(SOP)
            .where(and_(*conditions))
            .order_by(SOP.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        sops = result.scalars().all()
        
        return list(sops), total
    
    async def _generate_sop_content(
        self,
        interview: Interview,
        template: SOPTemplate | None,
    ) -> dict:
        """Generate SOP content from interview using AI."""
        # Get template sections
        sections = template.sections if template else self._default_sections()
        
        # Build prompt
        sections_prompt = "\n".join([
            f"- {s['title']}: {s.get('placeholder', '')}"
            for s in sections
        ])
        
        prompt = f"""
Generate a Standard Operating Procedure (SOP) from this interview content.

Interview Summary:
{interview.ai_summary or 'Not available'}

Extracted Procedures:
{interview.extracted_procedures}

Transcript Excerpt:
{interview.transcript_cleaned[:4000] if interview.transcript_cleaned else 'Not available'}

Key Insights:
{interview.key_insights}

The SOP should include these sections:
{sections_prompt}

Generate comprehensive content for each section based on the interview.
Include specific steps, safety considerations, and quality checkpoints.
"""
        
        schema = {
            "type": "object",
            "properties": {
                "purpose": {"type": "string"},
                "scope": {"type": "string"},
                "responsibilities": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "definitions": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
                "safety_requirements": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "equipment_needed": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "materials_needed": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "procedure_steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "step_number": {"type": "number"},
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "cautions": {"type": "array", "items": {"type": "string"}},
                            "notes": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
                "quality_checkpoints": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "troubleshooting": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "problem": {"type": "string"},
                            "cause": {"type": "string"},
                            "solution": {"type": "string"},
                        },
                    },
                },
                "references": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "confidence_score": {"type": "number"},
            },
        }
        
        content = await ai_client.generate_structured(
            prompt,
            schema,
            system_prompt="You are an SOP writer for manufacturing. Generate clear, actionable procedures.",
        )
        
        return content if isinstance(content, dict) else {}
    
    def _default_sections(self) -> list[dict]:
        """Return default SOP sections."""
        return [
            {"id": "purpose", "title": "Purpose", "required": True},
            {"id": "scope", "title": "Scope", "required": True},
            {"id": "responsibilities", "title": "Responsibilities", "required": True},
            {"id": "definitions", "title": "Definitions", "required": False},
            {"id": "safety", "title": "Safety Requirements", "required": True},
            {"id": "equipment", "title": "Equipment Needed", "required": True},
            {"id": "materials", "title": "Materials Needed", "required": False},
            {"id": "procedure", "title": "Procedure Steps", "required": True},
            {"id": "quality", "title": "Quality Checkpoints", "required": True},
            {"id": "troubleshooting", "title": "Troubleshooting", "required": False},
            {"id": "references", "title": "References", "required": False},
        ]
    
    def _content_to_plain_text(self, content: dict) -> str:
        """Convert SOP content to plain text for search."""
        text_parts = []
        
        for key, value in content.items():
            if isinstance(value, str):
                text_parts.append(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        text_parts.append(item)
                    elif isinstance(item, dict):
                        text_parts.extend(str(v) for v in item.values())
            elif isinstance(value, dict):
                text_parts.extend(str(v) for v in value.values())
        
        return " ".join(text_parts)
    
    async def _create_version(
        self,
        sop: SOP,
        change_summary: str,
        changed_by_id: str | None,
        change_type: str = "minor",
    ) -> SOPVersion:
        """Create a version snapshot."""
        version = SOPVersion(
            id=str(uuid4()),
            tenant_id=self.tenant_id,
            sop_id=sop.id,
            version_string=sop.version,
            content_snapshot=sop.content,
            change_summary=change_summary,
            change_type=change_type,
            changed_by_id=changed_by_id,
        )
        
        if change_type == "major" and changed_by_id:
            version.approved_by_id = changed_by_id
            version.approved_at = datetime.utcnow()
        
        self.session.add(version)
        return version
    
    async def _generate_sop_number(self) -> str:
        """Generate unique SOP number."""
        prefix = datetime.utcnow().strftime("SOP-%Y-")
        
        result = await self.session.execute(
            select(SOP.sop_number)
            .where(
                and_(
                    SOP.tenant_id == self.tenant_id,
                    SOP.sop_number.like(f"{prefix}%"),
                )
            )
            .order_by(SOP.sop_number.desc())
            .limit(1)
        )
        last_number = result.scalar_one_or_none()
        
        if last_number:
            seq = int(last_number.split("-")[-1])
            return f"{prefix}{seq + 1:04d}"
        
        return f"{prefix}0001"
    
    async def _count_unresolved_comments(self, sop_id: str) -> int:
        """Count unresolved required-action comments."""
        result = await self.session.execute(
            select(func.count(SOPReviewComment.id)).where(
                and_(
                    SOPReviewComment.sop_id == sop_id,
                    SOPReviewComment.tenant_id == self.tenant_id,
                    SOPReviewComment.requires_action == True,
                    SOPReviewComment.is_resolved == False,
                )
            )
        )
        return result.scalar_one()
    
    async def _get_interview(self, interview_id: str) -> Interview | None:
        """Get interview by ID."""
        result = await self.session.execute(
            select(Interview).where(
                and_(
                    Interview.id == interview_id,
                    Interview.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _get_template(self, template_id: str) -> SOPTemplate | None:
        """Get SOP template."""
        result = await self.session.execute(
            select(SOPTemplate).where(
                and_(
                    SOPTemplate.id == template_id,
                    SOPTemplate.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _get_knowledge_domain(self, domain_id: str) -> KnowledgeDomain | None:
        """Get knowledge domain."""
        result = await self.session.execute(
            select(KnowledgeDomain).where(
                and_(
                    KnowledgeDomain.id == domain_id,
                    KnowledgeDomain.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _find_default_template(self, category) -> SOPTemplate | None:
        """Find default template for category."""
        result = await self.session.execute(
            select(SOPTemplate).where(
                and_(
                    SOPTemplate.tenant_id == self.tenant_id,
                    SOPTemplate.is_default == True,
                    SOPTemplate.is_active == True,
                )
            ).limit(1)
        )
        return result.scalar_one_or_none()
