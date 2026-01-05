"""
Quote Intelligence System Service.

Provides functionality for:
- Parts matching with manufacturing nomenclature support
- Automated quote generation with AI assistance
- Historical quote lookup and analysis
- Quote version control and approval workflows
"""

from services.quote_intelligence.parts_service import PartsService
from services.quote_intelligence.quote_service import QuoteService
from services.quote_intelligence.matching_service import PartMatchingService
from services.quote_intelligence.pricing_service import PricingService

__all__ = [
    "PartsService",
    "QuoteService",
    "PartMatchingService",
    "PricingService",
]
