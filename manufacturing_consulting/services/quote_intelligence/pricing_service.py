"""
Pricing service for quote intelligence.

Provides AI-assisted pricing recommendations based on historical data,
material costs, and market analysis.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.quote_intelligence import (
    Part, Quote, QuoteLineItem, Customer, QuoteStatus
)
from utils.logging import ServiceLogger
from utils.ai_client import ai_client, prompt_builder
from config.settings import settings


@dataclass
class PricingRecommendation:
    """Pricing recommendation for a part."""
    part_id: str
    recommended_price: Decimal
    confidence: float
    price_range_low: Decimal
    price_range_high: Decimal
    basis: str  # historical, cost_plus, market, ai
    factors: list[str]
    historical_quotes: int


@dataclass
class QuotePricingSummary:
    """Summary of pricing analysis for a complete quote."""
    subtotal: Decimal
    suggested_discount: float
    margin_estimate: float
    confidence_score: float
    recommendations: list[str]
    risk_factors: list[str]


class PricingService:
    """
    Service for pricing analysis and recommendations.
    
    Provides:
    - Historical price analysis
    - AI-assisted pricing recommendations
    - Margin calculations
    - Volume discount suggestions
    - Customer-specific pricing
    """
    
    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.logger = ServiceLogger("pricing")
        self.confidence_threshold = settings.quote_intelligence.pricing_confidence_threshold
    
    async def get_price_recommendation(
        self,
        part_id: str,
        quantity: float = 1,
        customer_id: str | None = None,
    ) -> PricingRecommendation:
        """
        Get pricing recommendation for a part.
        
        Args:
            part_id: Part to price
            quantity: Order quantity
            customer_id: Optional customer for tier pricing
            
        Returns:
            PricingRecommendation with suggested price
        """
        self.logger.log_operation_start(
            "get_price_recommendation",
            tenant_id=self.tenant_id,
            part_id=part_id,
        )
        
        # Get part details
        part = await self._get_part(part_id)
        if not part:
            raise ValueError(f"Part not found: {part_id}")
        
        # Get historical pricing data
        historical = await self._get_historical_prices(part_id, customer_id)
        
        # Get customer pricing tier
        customer_discount = 0.0
        if customer_id:
            customer_discount = await self._get_customer_discount(customer_id)
        
        # Calculate recommendation
        if historical["count"] >= 3:
            # Enough historical data
            base_price = historical["avg_price"]
            confidence = min(0.95, 0.7 + (historical["count"] * 0.05))
            basis = "historical"
        elif part.list_price:
            # Use list price
            base_price = float(part.list_price)
            confidence = 0.8
            basis = "list_price"
        elif part.unit_cost:
            # Cost-plus pricing
            base_price = float(part.unit_cost) * 1.35  # 35% markup
            confidence = 0.6
            basis = "cost_plus"
        else:
            # Need AI recommendation
            base_price = await self._get_ai_price_recommendation(part)
            confidence = 0.5
            basis = "ai"
        
        # Apply quantity discount
        quantity_factor = self._calculate_quantity_discount(quantity)
        adjusted_price = base_price * quantity_factor
        
        # Apply customer discount
        final_price = adjusted_price * (1 - customer_discount)
        
        # Calculate price range
        variance = 0.1 if confidence >= 0.8 else 0.2
        price_low = final_price * (1 - variance)
        price_high = final_price * (1 + variance)
        
        factors = []
        if quantity > 1:
            factors.append(f"Quantity discount applied: {(1 - quantity_factor) * 100:.1f}%")
        if customer_discount > 0:
            factors.append(f"Customer tier discount: {customer_discount * 100:.1f}%")
        if historical["count"] > 0:
            factors.append(f"Based on {historical['count']} historical quotes")
        
        recommendation = PricingRecommendation(
            part_id=part_id,
            recommended_price=Decimal(str(round(final_price, 2))),
            confidence=confidence,
            price_range_low=Decimal(str(round(price_low, 2))),
            price_range_high=Decimal(str(round(price_high, 2))),
            basis=basis,
            factors=factors,
            historical_quotes=historical["count"],
        )
        
        self.logger.log_operation_complete(
            "get_price_recommendation",
            tenant_id=self.tenant_id,
            recommended_price=float(recommendation.recommended_price),
            confidence=recommendation.confidence,
        )
        
        return recommendation
    
    async def analyze_quote_pricing(
        self,
        quote_id: str,
    ) -> QuotePricingSummary:
        """
        Analyze pricing for an entire quote.
        
        Args:
            quote_id: Quote to analyze
            
        Returns:
            QuotePricingSummary with analysis
        """
        # Get quote with line items
        quote_result = await self.session.execute(
            select(Quote).where(
                and_(
                    Quote.id == quote_id,
                    Quote.tenant_id == self.tenant_id,
                )
            )
        )
        quote = quote_result.scalar_one_or_none()
        if not quote:
            raise ValueError(f"Quote not found: {quote_id}")
        
        # Get line items
        items_result = await self.session.execute(
            select(QuoteLineItem).where(
                and_(
                    QuoteLineItem.quote_id == quote_id,
                    QuoteLineItem.tenant_id == self.tenant_id,
                )
            )
        )
        line_items = items_result.scalars().all()
        
        # Analyze each line item
        total_recommended = Decimal("0")
        total_quoted = Decimal("0")
        total_cost = Decimal("0")
        recommendations = []
        risk_factors = []
        confidence_scores = []
        
        for item in line_items:
            if item.part_id:
                rec = await self.get_price_recommendation(
                    item.part_id,
                    float(item.quantity),
                    quote.customer_id,
                )
                
                line_recommended = rec.recommended_price * Decimal(str(item.quantity))
                total_recommended += line_recommended
                confidence_scores.append(rec.confidence)
                
                # Check if quoted price is significantly different
                quoted_extended = item.extended_price
                price_diff = float(quoted_extended - line_recommended) / float(line_recommended) if line_recommended > 0 else 0
                
                if price_diff > 0.15:
                    recommendations.append(
                        f"Line {item.line_number}: Quoted {price_diff:.0%} above recommended price"
                    )
                elif price_diff < -0.15:
                    risk_factors.append(
                        f"Line {item.line_number}: Quoted {abs(price_diff):.0%} below recommended price"
                    )
                
                # Track costs for margin
                part = await self._get_part(item.part_id)
                if part and part.unit_cost:
                    total_cost += Decimal(str(part.unit_cost)) * Decimal(str(item.quantity))
            
            total_quoted += item.extended_price
        
        # Calculate overall metrics
        margin_estimate = 0.0
        if total_quoted > 0 and total_cost > 0:
            margin_estimate = float((total_quoted - total_cost) / total_quoted)
        
        suggested_discount = 0.0
        if total_quoted > total_recommended * Decimal("1.1"):
            suggested_discount = float((total_quoted - total_recommended) / total_quoted) * 0.5
        
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5
        
        # Add margin recommendations
        if margin_estimate < 0.15:
            risk_factors.append(f"Low margin estimate: {margin_estimate:.0%}")
        elif margin_estimate > 0.5:
            recommendations.append(f"High margin: Consider discount to improve win rate")
        
        return QuotePricingSummary(
            subtotal=total_quoted,
            suggested_discount=suggested_discount,
            margin_estimate=margin_estimate,
            confidence_score=avg_confidence,
            recommendations=recommendations,
            risk_factors=risk_factors,
        )
    
    async def get_price_history(
        self,
        part_id: str,
        customer_id: str | None = None,
        months: int = 12,
    ) -> list[dict]:
        """
        Get price history for a part.
        
        Args:
            part_id: Part to get history for
            customer_id: Optional filter by customer
            months: How many months of history
            
        Returns:
            List of historical price points
        """
        cutoff_date = datetime.utcnow() - timedelta(days=months * 30)
        
        conditions = [
            QuoteLineItem.tenant_id == self.tenant_id,
            QuoteLineItem.part_id == part_id,
            Quote.status.in_([QuoteStatus.ACCEPTED, QuoteStatus.SENT]),
            Quote.quote_date >= cutoff_date,
        ]
        
        if customer_id:
            conditions.append(Quote.customer_id == customer_id)
        
        result = await self.session.execute(
            select(
                QuoteLineItem.unit_price,
                QuoteLineItem.quantity,
                Quote.quote_date,
                Quote.customer_id,
            )
            .join(Quote, Quote.id == QuoteLineItem.quote_id)
            .where(and_(*conditions))
            .order_by(Quote.quote_date.desc())
        )
        
        return [
            {
                "unit_price": float(row.unit_price),
                "quantity": float(row.quantity),
                "date": row.quote_date.isoformat(),
                "customer_id": row.customer_id,
            }
            for row in result.all()
        ]
    
    async def _get_part(self, part_id: str) -> Part | None:
        """Get part by ID."""
        result = await self.session.execute(
            select(Part).where(
                and_(
                    Part.id == part_id,
                    Part.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _get_historical_prices(
        self,
        part_id: str,
        customer_id: str | None = None,
    ) -> dict:
        """Get historical pricing statistics."""
        cutoff_date = datetime.utcnow() - timedelta(days=365)
        
        conditions = [
            QuoteLineItem.tenant_id == self.tenant_id,
            QuoteLineItem.part_id == part_id,
            Quote.status.in_([QuoteStatus.ACCEPTED, QuoteStatus.SENT]),
            Quote.quote_date >= cutoff_date,
        ]
        
        if customer_id:
            conditions.append(Quote.customer_id == customer_id)
        
        result = await self.session.execute(
            select(
                func.count(QuoteLineItem.id).label("count"),
                func.avg(QuoteLineItem.unit_price).label("avg_price"),
                func.min(QuoteLineItem.unit_price).label("min_price"),
                func.max(QuoteLineItem.unit_price).label("max_price"),
            )
            .join(Quote, Quote.id == QuoteLineItem.quote_id)
            .where(and_(*conditions))
        )
        
        row = result.one()
        return {
            "count": row.count or 0,
            "avg_price": float(row.avg_price) if row.avg_price else 0,
            "min_price": float(row.min_price) if row.min_price else 0,
            "max_price": float(row.max_price) if row.max_price else 0,
        }
    
    async def _get_customer_discount(self, customer_id: str) -> float:
        """Get customer's discount tier."""
        result = await self.session.execute(
            select(Customer.discount_percentage).where(
                and_(
                    Customer.id == customer_id,
                    Customer.tenant_id == self.tenant_id,
                )
            )
        )
        discount = result.scalar_one_or_none()
        return float(discount) / 100 if discount else 0.0
    
    def _calculate_quantity_discount(self, quantity: float) -> float:
        """Calculate quantity-based discount factor."""
        if quantity >= 1000:
            return 0.85  # 15% discount
        elif quantity >= 500:
            return 0.90  # 10% discount
        elif quantity >= 100:
            return 0.95  # 5% discount
        elif quantity >= 50:
            return 0.97  # 3% discount
        return 1.0
    
    async def _get_ai_price_recommendation(self, part: Part) -> float:
        """Get AI-based price recommendation when no historical data."""
        prompt = f"""
Recommend a unit price for this manufacturing part.

Part Information:
- Name: {part.name}
- Description: {part.description or 'N/A'}
- Category: {part.category.value if part.category else 'component'}
- Materials: {', '.join(part.materials) if part.materials else 'N/A'}
- Specifications: {part.specifications or 'N/A'}

Consider typical manufacturing costs, materials, and market rates.
Respond with just a number representing the recommended USD price.
"""
        
        try:
            response = await ai_client.generate_text(
                prompt,
                system_prompt="You are a manufacturing pricing expert. Provide realistic prices based on industry standards.",
                max_tokens=50,
            )
            
            # Extract number from response
            import re
            price_match = re.search(r'[\d,]+\.?\d*', response.replace(',', ''))
            if price_match:
                return float(price_match.group())
        except Exception as e:
            self.logger.log_operation_failed(
                "ai_price_recommendation",
                e,
                tenant_id=self.tenant_id,
            )
        
        # Fallback default
        return 100.0
