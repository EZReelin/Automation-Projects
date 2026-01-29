"""
Quote Intelligence System API routes.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from api.dependencies import (
    DatabaseDep, CurrentUserDep, TenantDep,
    require_permission, require_service
)
from services.quote_intelligence import QuoteService, PartsService, PartMatchingService, PricingService
from models.quote_intelligence import QuoteStatus, QuotePriority, PartCategory
from models.tenant import ServiceType

router = APIRouter(
    dependencies=[Depends(require_service(ServiceType.QUOTE_INTELLIGENCE))]
)


# Schemas
class PartCreate(BaseModel):
    part_number: str
    name: str
    description: str | None = None
    category: PartCategory = PartCategory.COMPONENT
    unit_cost: float | None = None
    list_price: float | None = None
    tags: list[str] = []


class LineItemCreate(BaseModel):
    part_id: str | None = None
    custom_part_number: str | None = None
    custom_description: str | None = None
    quantity: float = 1
    unit_price: float | None = None
    discount_percent: float = 0


class QuoteCreate(BaseModel):
    customer_id: str
    line_items: list[LineItemCreate]
    template_id: str | None = None
    reference: str | None = None
    notes: str | None = None
    priority: QuotePriority = QuotePriority.NORMAL


class QuoteGenerateRequest(BaseModel):
    customer_id: str
    request_text: str


class QuoteUpdate(BaseModel):
    notes: str | None = None
    priority: QuotePriority | None = None
    payment_terms: str | None = None
    delivery_terms: str | None = None


# Parts endpoints
@router.get("/parts")
async def list_parts(
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
    query: str | None = None,
    category: PartCategory | None = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
):
    """List parts with optional filtering."""
    service = PartsService(db, tenant_id)
    parts, total = await service.search_parts(
        query=query,
        category=category,
        limit=limit,
        offset=offset,
    )
    
    return {
        "items": [{"id": p.id, "part_number": p.part_number, "name": p.name, "category": p.category.value} for p in parts],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/parts", dependencies=[Depends(require_permission("quotes.manage"))])
async def create_part(
    body: PartCreate,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Create a new part in the catalog."""
    service = PartsService(db, tenant_id)
    
    part = await service.create_part(
        part_number=body.part_number,
        name=body.name,
        description=body.description,
        category=body.category,
        unit_cost=body.unit_cost,
        list_price=body.list_price,
        tags=body.tags,
    )
    
    return {"id": part.id, "part_number": part.part_number}


@router.get("/parts/{part_id}")
async def get_part(
    part_id: str,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Get a specific part."""
    service = PartsService(db, tenant_id)
    part = await service.get_part(part_id)
    
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    
    return {
        "id": part.id,
        "part_number": part.part_number,
        "name": part.name,
        "description": part.description,
        "category": part.category.value,
        "unit_cost": float(part.unit_cost) if part.unit_cost else None,
        "list_price": float(part.list_price) if part.list_price else None,
        "tags": part.tags,
    }


@router.get("/parts/{part_id}/similar")
async def get_similar_parts(
    part_id: str,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
    limit: int = Query(10, le=20),
):
    """Get similar parts for a given part."""
    service = PartMatchingService(db, tenant_id)
    similar = await service.get_similar_parts(part_id, limit=limit)
    
    return {
        "items": [
            {"id": p.id, "part_number": p.part_number, "name": p.name, "similarity": score}
            for p, score in similar
        ]
    }


@router.post("/parts/match")
async def match_parts(
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
    query: str = Query(..., description="Part description or number to match"),
    limit: int = Query(10, le=20),
):
    """Find matching parts for a description or part number."""
    service = PartMatchingService(db, tenant_id)
    matches = await service.find_matches(query, limit=limit)
    
    return {
        "items": [
            {
                "id": m.part.id,
                "part_number": m.part.part_number,
                "name": m.part.name,
                "score": m.score,
                "match_type": m.match_type,
                "match_reasons": m.match_reasons,
            }
            for m in matches
        ]
    }


# Quotes endpoints
@router.get("/")
async def list_quotes(
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
    query: str | None = None,
    customer_id: str | None = None,
    status: QuoteStatus | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
):
    """List quotes with filtering."""
    service = QuoteService(db, tenant_id)
    quotes, total = await service.search_quotes(
        query=query,
        customer_id=customer_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    
    return {
        "items": [
            {
                "id": q.id,
                "quote_number": q.quote_number,
                "customer_id": q.customer_id,
                "status": q.status.value,
                "total_amount": float(q.total_amount),
                "created_at": q.created_at.isoformat(),
            }
            for q in quotes
        ],
        "total": total,
    }


@router.post("/", dependencies=[Depends(require_permission("quotes.manage"))])
async def create_quote(
    body: QuoteCreate,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Create a new quote."""
    service = QuoteService(db, tenant_id)
    
    line_items = [item.model_dump() for item in body.line_items]
    
    quote = await service.create_quote(
        customer_id=body.customer_id,
        line_items=line_items,
        template_id=body.template_id,
        reference=body.reference,
        notes=body.notes,
        priority=body.priority,
        created_by_id=current_user["sub"],
    )
    
    return {"id": quote.id, "quote_number": quote.quote_number}


@router.post("/generate", dependencies=[Depends(require_permission("quotes.manage"))])
async def generate_quote(
    body: QuoteGenerateRequest,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Generate a quote from a natural language request."""
    service = QuoteService(db, tenant_id)
    
    quote = await service.generate_quote_from_request(
        customer_id=body.customer_id,
        request_text=body.request_text,
        created_by_id=current_user["sub"],
    )
    
    return {
        "id": quote.id,
        "quote_number": quote.quote_number,
        "ai_generated": quote.ai_generated,
        "ai_suggestions": quote.ai_suggestions,
    }


@router.get("/{quote_id}")
async def get_quote(
    quote_id: str,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Get a specific quote with line items."""
    service = QuoteService(db, tenant_id)
    quote = await service.get_quote(quote_id)
    
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    return {
        "id": quote.id,
        "quote_number": quote.quote_number,
        "version": quote.version,
        "customer_id": quote.customer_id,
        "status": quote.status.value,
        "priority": quote.priority.value,
        "subtotal": float(quote.subtotal),
        "discount_amount": float(quote.discount_amount),
        "tax_amount": float(quote.tax_amount),
        "total_amount": float(quote.total_amount),
        "notes": quote.notes,
        "valid_until": quote.valid_until.isoformat() if quote.valid_until else None,
        "created_at": quote.created_at.isoformat(),
        "line_items": [
            {
                "line_number": li.line_number,
                "part_id": li.part_id,
                "custom_part_number": li.custom_part_number,
                "quantity": float(li.quantity),
                "unit_price": float(li.unit_price),
                "extended_price": float(li.extended_price),
            }
            for li in quote.line_items
        ],
    }


@router.patch("/{quote_id}", dependencies=[Depends(require_permission("quotes.manage"))])
async def update_quote(
    quote_id: str,
    body: QuoteUpdate,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Update a quote."""
    service = QuoteService(db, tenant_id)
    
    updates = body.model_dump(exclude_unset=True)
    quote = await service.update_quote(
        quote_id=quote_id,
        updated_by_id=current_user["sub"],
        **updates,
    )
    
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    return {"id": quote.id, "status": quote.status.value}


@router.post("/{quote_id}/submit", dependencies=[Depends(require_permission("quotes.manage"))])
async def submit_quote_for_approval(
    quote_id: str,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Submit a quote for approval."""
    service = QuoteService(db, tenant_id)
    
    quote = await service.submit_for_approval(
        quote_id=quote_id,
        submitted_by_id=current_user["sub"],
    )
    
    if not quote:
        raise HTTPException(status_code=400, detail="Cannot submit this quote")
    
    return {"id": quote.id, "status": quote.status.value}


@router.post("/{quote_id}/approve", dependencies=[Depends(require_permission("quotes.approve"))])
async def approve_quote(
    quote_id: str,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Approve a quote."""
    service = QuoteService(db, tenant_id)
    
    quote = await service.approve_quote(
        quote_id=quote_id,
        approved_by_id=current_user["sub"],
    )
    
    if not quote:
        raise HTTPException(status_code=400, detail="Cannot approve this quote")
    
    return {"id": quote.id, "status": quote.status.value}


@router.get("/{quote_id}/pricing-analysis")
async def analyze_quote_pricing(
    quote_id: str,
    db: DatabaseDep,
    tenant_id: TenantDep,
    current_user: CurrentUserDep,
):
    """Get pricing analysis for a quote."""
    service = PricingService(db, tenant_id)
    
    try:
        analysis = await service.analyze_quote_pricing(quote_id)
        return {
            "subtotal": float(analysis.subtotal),
            "suggested_discount": analysis.suggested_discount,
            "margin_estimate": analysis.margin_estimate,
            "confidence_score": analysis.confidence_score,
            "recommendations": analysis.recommendations,
            "risk_factors": analysis.risk_factors,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
