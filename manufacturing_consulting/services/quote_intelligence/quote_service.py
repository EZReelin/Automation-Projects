"""
Quote management service.

Handles quote creation, generation, versioning, and approval workflows.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.quote_intelligence import (
    Quote, QuoteLineItem, QuoteVersion, QuoteAttachment,
    QuoteTemplate, Customer, Part, QuoteStatus, QuotePriority
)
from services.quote_intelligence.pricing_service import PricingService
from services.quote_intelligence.matching_service import PartMatchingService
from utils.logging import ServiceLogger
from utils.ai_client import ai_client, prompt_builder
from config.settings import settings


class QuoteService:
    """
    Service for managing quotes and quote generation.
    
    Provides:
    - Quote CRUD operations
    - AI-assisted quote generation
    - Version control
    - Approval workflows
    - Historical quote lookup
    """
    
    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.logger = ServiceLogger("quote")
        self.pricing_service = PricingService(session, tenant_id)
        self.matching_service = PartMatchingService(session, tenant_id)
    
    async def create_quote(
        self,
        customer_id: str,
        line_items: list[dict],
        template_id: str | None = None,
        reference: str | None = None,
        notes: str | None = None,
        created_by_id: str | None = None,
        **kwargs: Any,
    ) -> Quote:
        """
        Create a new quote.
        
        Args:
            customer_id: Customer for the quote
            line_items: List of line item dictionaries
            template_id: Optional quote template
            reference: Customer reference/PO
            notes: Quote notes
            created_by_id: Creating user ID
            **kwargs: Additional quote attributes
            
        Returns:
            Created Quote instance
        """
        self.logger.log_operation_start(
            "create_quote",
            tenant_id=self.tenant_id,
            customer_id=customer_id,
            line_count=len(line_items),
        )
        
        # Generate quote number
        quote_number = await self._generate_quote_number()
        
        # Get template for validity
        validity_days = settings.quote_intelligence.quote_validity_days
        if template_id:
            template_result = await self.session.execute(
                select(QuoteTemplate).where(QuoteTemplate.id == template_id)
            )
            template = template_result.scalar_one_or_none()
            if template:
                validity_days = template.validity_days
        
        # Create quote
        quote = Quote(
            id=str(uuid4()),
            tenant_id=self.tenant_id,
            quote_number=quote_number,
            customer_id=customer_id,
            template_id=template_id,
            reference=reference,
            notes=notes,
            created_by_id=created_by_id,
            valid_until=datetime.utcnow() + timedelta(days=validity_days),
            **kwargs,
        )
        
        self.session.add(quote)
        
        # Add line items
        subtotal = Decimal("0")
        for idx, item_data in enumerate(line_items, 1):
            line_item = await self._create_line_item(
                quote_id=quote.id,
                line_number=idx,
                **item_data,
            )
            subtotal += line_item.extended_price
        
        # Update totals
        quote.subtotal = subtotal
        quote.total_amount = subtotal - quote.discount_amount + quote.tax_amount + quote.shipping_amount
        
        await self.session.flush()
        
        # Create initial version
        await self._create_version(quote, "Initial quote created", created_by_id)
        
        self.logger.log_operation_complete(
            "create_quote",
            tenant_id=self.tenant_id,
            quote_id=quote.id,
            quote_number=quote_number,
        )
        
        return quote
    
    async def generate_quote_from_request(
        self,
        customer_id: str,
        request_text: str,
        created_by_id: str | None = None,
    ) -> Quote:
        """
        Generate a quote from a natural language request.
        
        Uses AI to parse the request, match parts, and generate pricing.
        
        Args:
            customer_id: Customer for the quote
            request_text: Natural language quote request
            created_by_id: Creating user ID
            
        Returns:
            Generated Quote instance
        """
        self.logger.log_operation_start(
            "generate_quote_from_request",
            tenant_id=self.tenant_id,
            customer_id=customer_id,
        )
        
        # Parse request using AI
        parsed = await self._parse_quote_request(request_text)
        
        # Match parts and build line items
        line_items = []
        for item in parsed.get("items", []):
            # Try to match to catalog
            matches = await self.matching_service.find_matches(
                item.get("description", ""),
                limit=1,
            )
            
            if matches and matches[0].score >= 0.8:
                # Use matched part
                matched_part = matches[0].part
                pricing = await self.pricing_service.get_price_recommendation(
                    matched_part.id,
                    item.get("quantity", 1),
                    customer_id,
                )
                
                line_items.append({
                    "part_id": matched_part.id,
                    "quantity": item.get("quantity", 1),
                    "unit_price": pricing.recommended_price,
                    "price_source": "ai",
                    "price_confidence": pricing.confidence,
                })
            else:
                # Custom item
                line_items.append({
                    "custom_part_number": item.get("part_number"),
                    "custom_description": item.get("description"),
                    "quantity": item.get("quantity", 1),
                    "unit_price": Decimal(str(item.get("estimated_price", 100))),
                    "price_source": "ai",
                    "price_confidence": 0.5,
                })
        
        # Create the quote
        quote = await self.create_quote(
            customer_id=customer_id,
            line_items=line_items,
            notes=parsed.get("notes"),
            created_by_id=created_by_id,
            ai_generated=True,
            ai_suggestions=parsed,
        )
        
        self.logger.log_operation_complete(
            "generate_quote_from_request",
            tenant_id=self.tenant_id,
            quote_id=quote.id,
        )
        
        return quote
    
    async def get_quote(
        self,
        quote_id: str,
        include_line_items: bool = True,
    ) -> Quote | None:
        """Get a quote by ID."""
        query = select(Quote).where(
            and_(
                Quote.id == quote_id,
                Quote.tenant_id == self.tenant_id,
            )
        )
        
        if include_line_items:
            query = query.options(selectinload(Quote.line_items))
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def update_quote(
        self,
        quote_id: str,
        updated_by_id: str | None = None,
        **updates: Any,
    ) -> Quote | None:
        """
        Update a quote and create a new version.
        
        Args:
            quote_id: Quote to update
            updated_by_id: User making the update
            **updates: Fields to update
            
        Returns:
            Updated Quote or None if not found
        """
        quote = await self.get_quote(quote_id)
        if not quote:
            return None
        
        # Don't allow updates to sent/accepted quotes
        if quote.status in [QuoteStatus.SENT, QuoteStatus.ACCEPTED]:
            # Create new version instead
            quote.version += 1
        
        for key, value in updates.items():
            if hasattr(quote, key) and key not in ["id", "tenant_id", "quote_number"]:
                setattr(quote, key, value)
        
        quote.updated_at = datetime.utcnow()
        
        # Create version snapshot
        await self._create_version(quote, "Quote updated", updated_by_id)
        
        await self.session.flush()
        return quote
    
    async def update_line_item(
        self,
        quote_id: str,
        line_number: int,
        updated_by_id: str | None = None,
        **updates: Any,
    ) -> QuoteLineItem | None:
        """Update a specific line item."""
        result = await self.session.execute(
            select(QuoteLineItem).where(
                and_(
                    QuoteLineItem.quote_id == quote_id,
                    QuoteLineItem.tenant_id == self.tenant_id,
                    QuoteLineItem.line_number == line_number,
                )
            )
        )
        line_item = result.scalar_one_or_none()
        if not line_item:
            return None
        
        for key, value in updates.items():
            if hasattr(line_item, key):
                setattr(line_item, key, value)
        
        # Recalculate extended price
        line_item.extended_price = (
            Decimal(str(line_item.quantity)) *
            line_item.unit_price *
            (Decimal("1") - Decimal(str(line_item.discount_percent)) / 100)
        )
        
        # Update quote totals
        await self._recalculate_quote_totals(quote_id)
        
        await self.session.flush()
        return line_item
    
    async def submit_for_approval(
        self,
        quote_id: str,
        submitted_by_id: str,
    ) -> Quote | None:
        """Submit a quote for approval."""
        quote = await self.get_quote(quote_id)
        if not quote or quote.status != QuoteStatus.DRAFT:
            return None
        
        quote.status = QuoteStatus.PENDING_REVIEW
        quote.updated_at = datetime.utcnow()
        
        await self._create_version(
            quote,
            "Submitted for approval",
            submitted_by_id,
        )
        
        await self.session.flush()
        return quote
    
    async def approve_quote(
        self,
        quote_id: str,
        approved_by_id: str,
    ) -> Quote | None:
        """Approve a quote."""
        quote = await self.get_quote(quote_id)
        if not quote or quote.status != QuoteStatus.PENDING_REVIEW:
            return None
        
        quote.status = QuoteStatus.APPROVED
        quote.approved_by_id = approved_by_id
        quote.approved_at = datetime.utcnow()
        quote.updated_at = datetime.utcnow()
        
        await self._create_version(
            quote,
            "Quote approved",
            approved_by_id,
        )
        
        await self.session.flush()
        return quote
    
    async def reject_quote(
        self,
        quote_id: str,
        rejected_by_id: str,
        reason: str,
    ) -> Quote | None:
        """Reject a quote."""
        quote = await self.get_quote(quote_id)
        if not quote:
            return None
        
        quote.status = QuoteStatus.REJECTED
        quote.rejection_reason = reason
        quote.updated_at = datetime.utcnow()
        
        await self._create_version(
            quote,
            f"Quote rejected: {reason}",
            rejected_by_id,
        )
        
        await self.session.flush()
        return quote
    
    async def search_quotes(
        self,
        query: str | None = None,
        customer_id: str | None = None,
        status: QuoteStatus | None = None,
        part_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Quote], int]:
        """
        Search quotes with various filters.
        
        Args:
            query: Text search in quote number, reference, notes
            customer_id: Filter by customer
            status: Filter by status
            part_type: Filter by part category in line items
            date_from: Start date filter
            date_to: End date filter
            price_min: Minimum total amount
            price_max: Maximum total amount
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            Tuple of (quotes list, total count)
        """
        conditions = [Quote.tenant_id == self.tenant_id]
        
        if query:
            search_pattern = f"%{query}%"
            conditions.append(
                or_(
                    Quote.quote_number.ilike(search_pattern),
                    Quote.reference.ilike(search_pattern),
                    Quote.notes.ilike(search_pattern),
                )
            )
        
        if customer_id:
            conditions.append(Quote.customer_id == customer_id)
        
        if status:
            conditions.append(Quote.status == status)
        
        if date_from:
            conditions.append(Quote.quote_date >= date_from)
        
        if date_to:
            conditions.append(Quote.quote_date <= date_to)
        
        if price_min is not None:
            conditions.append(Quote.total_amount >= price_min)
        
        if price_max is not None:
            conditions.append(Quote.total_amount <= price_max)
        
        # Get total count
        count_query = select(func.count(Quote.id)).where(and_(*conditions))
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()
        
        # Get quotes
        quotes_query = (
            select(Quote)
            .where(and_(*conditions))
            .options(selectinload(Quote.line_items))
            .order_by(Quote.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(quotes_query)
        quotes = result.scalars().all()
        
        return list(quotes), total
    
    async def get_similar_historical_quotes(
        self,
        parts: list[str],
        customer_id: str | None = None,
        limit: int = 5,
    ) -> list[Quote]:
        """
        Find historical quotes with similar parts.
        
        Args:
            parts: List of part IDs or descriptions
            customer_id: Optional filter by customer
            limit: Maximum results
            
        Returns:
            List of similar quotes
        """
        # Get quotes containing any of the specified parts
        conditions = [
            Quote.tenant_id == self.tenant_id,
            Quote.status.in_([QuoteStatus.ACCEPTED, QuoteStatus.SENT]),
        ]
        
        if customer_id:
            conditions.append(Quote.customer_id == customer_id)
        
        # Subquery for quotes with matching parts
        subquery = (
            select(QuoteLineItem.quote_id)
            .where(
                and_(
                    QuoteLineItem.tenant_id == self.tenant_id,
                    QuoteLineItem.part_id.in_(parts),
                )
            )
            .distinct()
        )
        
        conditions.append(Quote.id.in_(subquery))
        
        result = await self.session.execute(
            select(Quote)
            .where(and_(*conditions))
            .options(selectinload(Quote.line_items))
            .order_by(Quote.quote_date.desc())
            .limit(limit)
        )
        
        return list(result.scalars().all())
    
    async def _create_line_item(
        self,
        quote_id: str,
        line_number: int,
        part_id: str | None = None,
        custom_part_number: str | None = None,
        custom_description: str | None = None,
        quantity: float = 1,
        unit_price: Decimal | None = None,
        discount_percent: float = 0,
        **kwargs: Any,
    ) -> QuoteLineItem:
        """Create a quote line item."""
        # Get pricing if not provided
        if unit_price is None and part_id:
            pricing = await self.pricing_service.get_price_recommendation(
                part_id, quantity
            )
            unit_price = pricing.recommended_price
        
        unit_price = unit_price or Decimal("0")
        
        extended_price = (
            Decimal(str(quantity)) *
            unit_price *
            (Decimal("1") - Decimal(str(discount_percent)) / 100)
        )
        
        line_item = QuoteLineItem(
            id=str(uuid4()),
            tenant_id=self.tenant_id,
            quote_id=quote_id,
            line_number=line_number,
            part_id=part_id,
            custom_part_number=custom_part_number,
            custom_description=custom_description,
            quantity=quantity,
            unit_price=unit_price,
            discount_percent=discount_percent,
            extended_price=extended_price,
            **kwargs,
        )
        
        self.session.add(line_item)
        return line_item
    
    async def _create_version(
        self,
        quote: Quote,
        change_summary: str,
        changed_by_id: str | None,
    ) -> QuoteVersion:
        """Create a version snapshot of a quote."""
        # Build snapshot
        snapshot = {
            "quote_number": quote.quote_number,
            "version": quote.version,
            "status": quote.status.value,
            "customer_id": quote.customer_id,
            "subtotal": str(quote.subtotal),
            "discount_amount": str(quote.discount_amount),
            "tax_amount": str(quote.tax_amount),
            "total_amount": str(quote.total_amount),
            "notes": quote.notes,
            "valid_until": quote.valid_until.isoformat() if quote.valid_until else None,
        }
        
        version = QuoteVersion(
            id=str(uuid4()),
            tenant_id=self.tenant_id,
            quote_id=quote.id,
            version_number=quote.version,
            snapshot=snapshot,
            change_summary=change_summary,
            changed_by_id=changed_by_id,
        )
        
        self.session.add(version)
        return version
    
    async def _recalculate_quote_totals(self, quote_id: str) -> None:
        """Recalculate quote totals from line items."""
        result = await self.session.execute(
            select(func.sum(QuoteLineItem.extended_price)).where(
                and_(
                    QuoteLineItem.quote_id == quote_id,
                    QuoteLineItem.tenant_id == self.tenant_id,
                )
            )
        )
        subtotal = result.scalar_one() or Decimal("0")
        
        quote = await self.get_quote(quote_id, include_line_items=False)
        if quote:
            quote.subtotal = subtotal
            quote.total_amount = subtotal - quote.discount_amount + quote.tax_amount + quote.shipping_amount
    
    async def _generate_quote_number(self) -> str:
        """Generate a unique quote number."""
        # Format: Q-YYYYMM-XXXX
        prefix = datetime.utcnow().strftime("Q-%Y%m-")
        
        # Get latest quote number with this prefix
        result = await self.session.execute(
            select(Quote.quote_number)
            .where(
                and_(
                    Quote.tenant_id == self.tenant_id,
                    Quote.quote_number.like(f"{prefix}%"),
                )
            )
            .order_by(Quote.quote_number.desc())
            .limit(1)
        )
        last_number = result.scalar_one_or_none()
        
        if last_number:
            # Extract sequence and increment
            seq = int(last_number.split("-")[-1])
            return f"{prefix}{seq + 1:04d}"
        
        return f"{prefix}0001"
    
    async def _parse_quote_request(self, request_text: str) -> dict:
        """Parse a natural language quote request using AI."""
        schema = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "part_number": {"type": "string"},
                            "quantity": {"type": "number"},
                            "estimated_price": {"type": "number"},
                        },
                    },
                },
                "notes": {"type": "string"},
                "urgency": {"type": "string"},
            },
        }
        
        prompt = f"""
Parse this quote request and extract the items being requested.

Request:
{request_text}

Extract each item with its description, part number (if mentioned), and quantity.
If no quantity is specified, assume 1.
"""
        
        return await ai_client.generate_structured(
            prompt,
            schema,
            system_prompt="You are a manufacturing quote parser. Extract item details accurately.",
        )
