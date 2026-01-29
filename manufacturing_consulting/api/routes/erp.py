"""
ERP Copilot API routes.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel

from api.dependencies import (
    DatabaseDep, CurrentUserDep, TenantDep,
    require_permission, require_service
)
from services.erp_copilot import ERPQueryService, ERPDocumentService, ERPAnalyticsService
from models.erp_copilot import ERPSystem, DocumentType, QueryCategory
from models.tenant import ServiceType

router = APIRouter(
    dependencies=[Depends(require_service(ServiceType.ERP_COPILOT))]
)


# Schemas
class ERPConfigCreate(BaseModel):
    erp_system: ERPSystem
    system_version: str | None = None
    instance_name: str | None = None
    enabled_modules: list[str] = []
    custom_terminology: dict = {}


class DocumentCreate(BaseModel):
    title: str
    content: str
    document_type: DocumentType = DocumentType.OTHER
    module: str | None = None
    source_url: str | None = None
    erp_menu_path: str | None = None
    tags: list[str] = []


class QueryRequest(BaseModel):
    query: str
    conversation_id: str | None = None


class FeedbackRequest(BaseModel):
    rating: int | None = None
    was_helpful: bool | None = None
    feedback_text: str | None = None


class QueryTemplateCreate(BaseModel):
    name: str
    query_patterns: list[str]
    response_template: str
    category: QueryCategory | None = None
    module: str | None = None
    keywords: list[str] = []


# Configuration
@router.post("/config", dependencies=[Depends(require_permission("erp.manage"))])
async def configure_erp(
    body: ERPConfigCreate,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Configure ERP system for the tenant."""
    service = ERPDocumentService(db, tenant_id)
    
    config = await service.configure_erp(
        erp_system=body.erp_system,
        system_version=body.system_version,
        instance_name=body.instance_name,
        enabled_modules=body.enabled_modules,
        custom_terminology=body.custom_terminology,
    )
    
    return {
        "id": config.id,
        "erp_system": config.erp_system.value,
        "enabled_modules": config.enabled_modules,
    }


# Documents
@router.get("/documents")
async def list_documents(
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
    module: str | None = None,
    document_type: DocumentType | None = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
):
    """List ERP documents."""
    service = ERPDocumentService(db, tenant_id)
    documents, total = await service.list_documents(
        module=module,
        document_type=document_type,
        limit=limit,
        offset=offset,
    )
    
    return {
        "items": [
            {
                "id": d.id,
                "title": d.title,
                "document_type": d.document_type.value,
                "module": d.module,
                "is_processed": d.is_processed,
            }
            for d in documents
        ],
        "total": total,
    }


@router.post("/documents", dependencies=[Depends(require_permission("erp.manage"))])
async def create_document(
    body: DocumentCreate,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Ingest a new ERP document."""
    service = ERPDocumentService(db, tenant_id)
    
    try:
        document = await service.ingest_document(
            title=body.title,
            content=body.content,
            document_type=body.document_type,
            module=body.module,
            source_url=body.source_url,
            erp_menu_path=body.erp_menu_path,
            tags=body.tags,
        )
        
        return {
            "id": document.id,
            "title": document.title,
            "is_processed": document.is_processed,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/documents/upload", dependencies=[Depends(require_permission("erp.manage"))])
async def upload_document(
    file: UploadFile = File(...),
    document_type: DocumentType = DocumentType.OTHER,
    module: str | None = None,
    db: DatabaseDep = None,
    tenant_id: TenantDep = None,
    current_user: CurrentUserDep = None,
):
    """Upload and ingest a document file."""
    service = ERPDocumentService(db, tenant_id)
    
    try:
        document = await service.ingest_document_file(
            file=file.file,
            filename=file.filename,
            document_type=document_type,
            module=module,
        )
        
        return {
            "id": document.id,
            "title": document.title,
            "is_processed": document.is_processed,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Get a specific document."""
    service = ERPDocumentService(db, tenant_id)
    document = await service.get_document(document_id)
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "id": document.id,
        "title": document.title,
        "document_type": document.document_type.value,
        "module": document.module,
        "content_summary": document.content_summary,
        "keywords": document.keywords,
        "tags": document.tags,
        "erp_menu_path": document.erp_menu_path,
        "is_processed": document.is_processed,
    }


@router.delete("/documents/{document_id}", dependencies=[Depends(require_permission("erp.manage"))])
async def delete_document(
    document_id: str,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Delete a document."""
    service = ERPDocumentService(db, tenant_id)
    
    success = await service.delete_document(document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {"message": "Document deleted"}


# Queries
@router.post("/query")
async def query_erp(
    body: QueryRequest,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """
    Query ERP documentation using natural language.
    
    Returns AI-generated response based on indexed documentation.
    """
    service = ERPQueryService(db, tenant_id)
    
    result = await service.process_query(
        query_text=body.query,
        user_id=current_user["sub"],
        conversation_id=body.conversation_id,
    )
    
    return result


@router.post("/queries/{query_id}/feedback")
async def submit_query_feedback(
    query_id: str,
    body: FeedbackRequest,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Submit feedback for a query response."""
    service = ERPQueryService(db, tenant_id)
    
    query = await service.submit_feedback(
        query_id=query_id,
        rating=body.rating,
        was_helpful=body.was_helpful,
        feedback_text=body.feedback_text,
    )
    
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")
    
    return {"message": "Feedback submitted"}


@router.get("/conversation/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
    limit: int = Query(20, le=50),
):
    """Get conversation history."""
    service = ERPQueryService(db, tenant_id)
    queries = await service.get_conversation_history(conversation_id, limit=limit)
    
    return {
        "items": [
            {
                "id": q.id,
                "query": q.query_text,
                "response": q.response_text,
                "confidence": q.confidence_score,
                "created_at": q.created_at.isoformat(),
            }
            for q in queries
        ]
    }


# Query Templates
@router.get("/templates")
async def list_query_templates(
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
    category: QueryCategory | None = None,
    module: str | None = None,
):
    """List query templates."""
    service = ERPQueryService(db, tenant_id)
    templates = await service.list_templates(category=category, module=module)
    
    return {
        "items": [
            {
                "id": t.id,
                "name": t.name,
                "query_patterns": t.query_patterns,
                "category": t.category.value if t.category else None,
                "usage_count": t.usage_count,
            }
            for t in templates
        ]
    }


@router.post("/templates", dependencies=[Depends(require_permission("erp.manage"))])
async def create_query_template(
    body: QueryTemplateCreate,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Create a query template."""
    service = ERPQueryService(db, tenant_id)
    
    template = await service.create_query_template(
        name=body.name,
        query_patterns=body.query_patterns,
        response_template=body.response_template,
        category=body.category,
        module=body.module,
        keywords=body.keywords,
    )
    
    return {"id": template.id, "name": template.name}


# Analytics
@router.get("/analytics/summary")
async def get_analytics_summary(
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
    days: int = Query(30, ge=1, le=365),
):
    """Get usage analytics summary."""
    service = ERPAnalyticsService(db, tenant_id)
    summary = await service.get_usage_summary(days=days)
    
    return summary


@router.get("/analytics/by-category")
async def get_queries_by_category(
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
    days: int = Query(30, ge=1, le=365),
):
    """Get query breakdown by category."""
    service = ERPAnalyticsService(db, tenant_id)
    return {"items": await service.get_queries_by_category(days=days)}


@router.get("/analytics/trend")
async def get_daily_trend(
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
    days: int = Query(30, ge=1, le=90),
):
    """Get daily query trend."""
    service = ERPAnalyticsService(db, tenant_id)
    return {"items": await service.get_daily_trend(days=days)}


@router.get("/analytics/gaps")
async def get_documentation_gaps(
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
    severity: str | None = None,
    limit: int = Query(20, le=50),
):
    """Get identified documentation gaps."""
    service = ERPAnalyticsService(db, tenant_id)
    gaps = await service.get_documentation_gaps(severity=severity, limit=limit)
    
    return {
        "items": [
            {
                "id": g.id,
                "topic": g.topic,
                "module": g.module,
                "query_count": g.query_count,
                "severity": g.severity,
                "sample_queries": g.sample_queries[:3],
            }
            for g in gaps
        ]
    }


@router.post("/analytics/gaps/{gap_id}/resolve", dependencies=[Depends(require_permission("erp.manage"))])
async def resolve_documentation_gap(
    gap_id: str,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
    resolution_document_id: str | None = None,
    resolution_notes: str | None = None,
):
    """Mark a documentation gap as resolved."""
    service = ERPAnalyticsService(db, tenant_id)
    
    gap = await service.resolve_gap(
        gap_id=gap_id,
        resolution_document_id=resolution_document_id,
        resolution_notes=resolution_notes,
    )
    
    if not gap:
        raise HTTPException(status_code=404, detail="Gap not found")
    
    return {"message": "Gap resolved"}
