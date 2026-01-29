"""
Knowledge Preservation Package API routes.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.dependencies import (
    DatabaseDep, CurrentUserDep, TenantDep,
    require_permission, require_service
)
from services.knowledge_preservation import (
    InterviewService, SOPService, KnowledgeDomainService, ExportService
)
from models.knowledge_preservation import (
    KnowledgeDomainCategory, InterviewStatus, SOPStatus, SOPPriority
)
from models.tenant import ServiceType

router = APIRouter(
    dependencies=[Depends(require_service(ServiceType.KNOWLEDGE_PRESERVATION))]
)


# Schemas
class DomainCreate(BaseModel):
    name: str
    code: str
    description: str | None = None
    category: KnowledgeDomainCategory = KnowledgeDomainCategory.OTHER
    equipment_types: list[str] = []
    process_areas: list[str] = []


class SMECreate(BaseModel):
    first_name: str
    last_name: str
    email: str | None = None
    department: str | None = None
    job_title: str | None = None
    years_of_experience: int | None = None
    is_retiring: bool = False
    expected_departure_date: datetime | None = None
    expertise_areas: list[str] = []


class InterviewSchedule(BaseModel):
    title: str
    knowledge_domain_id: str
    sme_id: str
    scheduled_date: datetime
    description: str | None = None
    template_id: str | None = None


class TranscriptSubmit(BaseModel):
    transcript: str


class SOPCreate(BaseModel):
    title: str
    knowledge_domain_id: str
    content: dict
    template_id: str | None = None


class ReviewComment(BaseModel):
    comment_text: str
    section_reference: str | None = None
    requires_action: bool = False


# Knowledge Domains
@router.get("/domains")
async def list_domains(
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
    category: KnowledgeDomainCategory | None = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
):
    """List knowledge domains."""
    service = KnowledgeDomainService(db, tenant_id)
    domains, total = await service.list_domains(
        category=category,
        limit=limit,
        offset=offset,
    )
    
    return {
        "items": [
            {
                "id": d.id,
                "name": d.name,
                "code": d.code,
                "category": d.category.value,
                "completion_percentage": d.completion_percentage,
            }
            for d in domains
        ],
        "total": total,
    }


@router.post("/domains", dependencies=[Depends(require_permission("sops.manage"))])
async def create_domain(
    body: DomainCreate,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Create a new knowledge domain."""
    service = KnowledgeDomainService(db, tenant_id)
    
    domain = await service.create_domain(
        name=body.name,
        code=body.code,
        description=body.description,
        category=body.category,
        equipment_types=body.equipment_types,
        process_areas=body.process_areas,
    )
    
    return {"id": domain.id, "code": domain.code}


@router.get("/domains/{domain_id}")
async def get_domain(
    domain_id: str,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Get a knowledge domain with progress."""
    service = KnowledgeDomainService(db, tenant_id)
    
    domain = await service.get_domain(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    progress = await service.get_domain_progress(domain_id)
    
    return {
        "id": domain.id,
        "name": domain.name,
        "code": domain.code,
        "description": domain.description,
        "category": domain.category.value,
        "equipment_types": domain.equipment_types,
        "process_areas": domain.process_areas,
        "progress": progress,
    }


# Subject Matter Experts
@router.get("/smes")
async def list_smes(
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
    is_retiring: bool | None = None,
    department: str | None = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
):
    """List subject matter experts."""
    service = KnowledgeDomainService(db, tenant_id)
    smes, total = await service.list_smes(
        is_retiring=is_retiring,
        department=department,
        limit=limit,
        offset=offset,
    )
    
    return {
        "items": [
            {
                "id": s.id,
                "name": s.full_name,
                "department": s.department,
                "job_title": s.job_title,
                "is_retiring": s.is_retiring,
                "expected_departure_date": s.expected_departure_date.isoformat() if s.expected_departure_date else None,
            }
            for s in smes
        ],
        "total": total,
    }


@router.post("/smes", dependencies=[Depends(require_permission("sops.manage"))])
async def create_sme(
    body: SMECreate,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Create a subject matter expert record."""
    service = KnowledgeDomainService(db, tenant_id)
    
    sme = await service.create_sme(**body.model_dump())
    
    return {"id": sme.id, "name": sme.full_name}


@router.get("/smes/priority")
async def get_retiring_smes_priority(
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Get retiring SMEs sorted by knowledge capture priority."""
    service = KnowledgeDomainService(db, tenant_id)
    prioritized = await service.get_retiring_smes_priority()
    
    return {
        "items": [
            {
                "sme_id": item["sme"].id,
                "name": item["sme"].full_name,
                "department": item["sme"].department,
                "days_until_departure": item["days_until_departure"],
                "interviews_completed": item["interviews_completed"],
                "priority_score": item["priority_score"],
            }
            for item in prioritized
        ]
    }


# Interviews
@router.get("/interviews")
async def list_interviews(
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
    domain_id: str | None = None,
    sme_id: str | None = None,
    status: InterviewStatus | None = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
):
    """List interviews."""
    service = InterviewService(db, tenant_id)
    interviews, total = await service.list_interviews(
        knowledge_domain_id=domain_id,
        sme_id=sme_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    
    return {
        "items": [
            {
                "id": i.id,
                "title": i.title,
                "status": i.status.value,
                "scheduled_date": i.scheduled_date.isoformat() if i.scheduled_date else None,
                "duration_minutes": i.duration_minutes,
            }
            for i in interviews
        ],
        "total": total,
    }


@router.post("/interviews", dependencies=[Depends(require_permission("sops.manage"))])
async def schedule_interview(
    body: InterviewSchedule,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Schedule a new interview."""
    service = InterviewService(db, tenant_id)
    
    interview = await service.schedule_interview(
        title=body.title,
        knowledge_domain_id=body.knowledge_domain_id,
        sme_id=body.sme_id,
        scheduled_date=body.scheduled_date,
        interviewer_id=current_user["sub"],
        template_id=body.template_id,
        description=body.description,
    )
    
    return {"id": interview.id, "title": interview.title}


@router.post("/interviews/{interview_id}/start", dependencies=[Depends(require_permission("sops.manage"))])
async def start_interview(
    interview_id: str,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Mark interview as started."""
    service = InterviewService(db, tenant_id)
    
    interview = await service.start_interview(interview_id)
    if not interview:
        raise HTTPException(status_code=400, detail="Cannot start this interview")
    
    return {"id": interview.id, "status": interview.status.value}


@router.post("/interviews/{interview_id}/transcript", dependencies=[Depends(require_permission("sops.manage"))])
async def submit_transcript(
    interview_id: str,
    body: TranscriptSubmit,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Submit interview transcript for processing."""
    service = InterviewService(db, tenant_id)
    
    interview = await service.submit_transcript(
        interview_id=interview_id,
        transcript=body.transcript,
    )
    
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    return {
        "id": interview.id,
        "status": interview.status.value,
        "ai_summary": interview.ai_summary,
        "extracted_topics": interview.extracted_topics,
    }


@router.get("/interviews/{interview_id}/follow-ups")
async def get_follow_up_questions(
    interview_id: str,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Get AI-suggested follow-up questions."""
    service = InterviewService(db, tenant_id)
    questions = await service.suggest_follow_up_questions(interview_id)
    
    return {"questions": questions}


# SOPs
@router.get("/sops")
async def list_sops(
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
    query: str | None = None,
    domain_id: str | None = None,
    status: SOPStatus | None = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
):
    """List SOPs."""
    service = SOPService(db, tenant_id)
    sops, total = await service.search_sops(
        query=query,
        knowledge_domain_id=domain_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    
    return {
        "items": [
            {
                "id": s.id,
                "sop_number": s.sop_number,
                "title": s.title,
                "version": s.version,
                "status": s.status.value,
                "ai_generated": s.ai_generated,
            }
            for s in sops
        ],
        "total": total,
    }


@router.post("/sops/generate", dependencies=[Depends(require_permission("sops.manage"))])
async def generate_sop_from_interview(
    interview_id: str,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
    template_id: str | None = None,
):
    """Generate an SOP from a processed interview."""
    service = SOPService(db, tenant_id)
    
    try:
        sop = await service.generate_sop_from_interview(
            interview_id=interview_id,
            template_id=template_id,
            created_by_id=current_user["sub"],
        )
        
        return {
            "id": sop.id,
            "sop_number": sop.sop_number,
            "title": sop.title,
            "ai_confidence_score": sop.ai_confidence_score,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sops/{sop_id}")
async def get_sop(
    sop_id: str,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Get an SOP with content."""
    service = SOPService(db, tenant_id)
    sop = await service.get_sop(sop_id)
    
    if not sop:
        raise HTTPException(status_code=404, detail="SOP not found")
    
    return {
        "id": sop.id,
        "sop_number": sop.sop_number,
        "title": sop.title,
        "version": sop.version,
        "status": sop.status.value,
        "content": sop.content,
        "ai_generated": sop.ai_generated,
        "ai_confidence_score": sop.ai_confidence_score,
        "effective_date": sop.effective_date.isoformat() if sop.effective_date else None,
        "review_comments": [
            {
                "id": c.id,
                "comment_text": c.comment_text,
                "section_reference": c.section_reference,
                "requires_action": c.requires_action,
                "is_resolved": c.is_resolved,
            }
            for c in sop.review_comments
        ],
    }


@router.post("/sops/{sop_id}/review-comments", dependencies=[Depends(require_permission("sops.approve"))])
async def add_review_comment(
    sop_id: str,
    body: ReviewComment,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Add a review comment to an SOP."""
    service = SOPService(db, tenant_id)
    
    comment = await service.add_review_comment(
        sop_id=sop_id,
        author_id=current_user["sub"],
        comment_text=body.comment_text,
        section_reference=body.section_reference,
        requires_action=body.requires_action,
    )
    
    return {"id": comment.id}


@router.post("/sops/{sop_id}/approve", dependencies=[Depends(require_permission("sops.approve"))])
async def approve_sop(
    sop_id: str,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Approve an SOP."""
    service = SOPService(db, tenant_id)
    
    try:
        sop = await service.approve_sop(
            sop_id=sop_id,
            approved_by_id=current_user["sub"],
        )
        
        if not sop:
            raise HTTPException(status_code=400, detail="Cannot approve this SOP")
        
        return {"id": sop.id, "status": sop.status.value}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sops/{sop_id}/export/{format}")
async def export_sop(
    sop_id: str,
    format: str,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Export SOP to specified format (markdown, html, docx, pdf)."""
    sop_service = SOPService(db, tenant_id)
    export_service = ExportService(db, tenant_id)
    
    sop = await sop_service.get_sop(sop_id)
    if not sop:
        raise HTTPException(status_code=404, detail="SOP not found")
    
    if format == "markdown":
        content = await export_service.export_sop_to_markdown(sop)
        return {"content": content, "format": "markdown"}
    
    elif format == "html":
        content = await export_service.export_sop_to_html(sop)
        return {"content": content, "format": "html"}
    
    elif format == "docx":
        buffer = await export_service.export_sop_to_docx(sop)
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{sop.sop_number}.docx"'},
        )
    
    elif format == "pdf":
        buffer = await export_service.export_sop_to_pdf(sop)
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{sop.sop_number}.pdf"'},
        )
    
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")


@router.get("/gaps")
async def get_knowledge_gaps(
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Identify knowledge gaps in the organization."""
    service = KnowledgeDomainService(db, tenant_id)
    gaps = await service.get_knowledge_gaps()
    
    return {
        "items": [
            {
                "domain_id": g["domain"].id,
                "domain_name": g["domain"].name,
                "progress": g["progress"],
                "gap_reasons": g["gap_reasons"],
            }
            for g in gaps
        ]
    }
