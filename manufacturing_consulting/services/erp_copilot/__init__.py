"""
ERP Copilot Service.

Provides functionality for:
- Natural language query interface for ERP systems
- Documentation indexing and retrieval
- Context-aware responses
- Usage analytics and gap identification
"""

from services.erp_copilot.query_service import ERPQueryService
from services.erp_copilot.document_service import ERPDocumentService
from services.erp_copilot.analytics_service import ERPAnalyticsService

__all__ = [
    "ERPQueryService",
    "ERPDocumentService",
    "ERPAnalyticsService",
]
