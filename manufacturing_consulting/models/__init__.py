"""
Data models for the Manufacturing Consulting System.

This module provides SQLAlchemy ORM models for:
- Multi-tenant architecture (tenants, subscriptions, API keys)
- User management and authentication
- Quote Intelligence System (parts, quotes, customers)
- Knowledge Preservation Package (interviews, SOPs, knowledge domains)
- ERP Copilot (documents, queries, analytics)
"""

from models.tenant import (
    Tenant,
    TenantSubscription,
    TenantAPIKey,
    UsageRecord,
    SubscriptionTier,
    SubscriptionStatus,
    ServiceType,
)

from models.user import (
    User,
    UserSession,
    AuditLog,
    UserRole,
    SystemRole,
    ROLE_PERMISSIONS,
)

from models.quote_intelligence import (
    Part,
    PartSimilarity,
    Customer,
    QuoteTemplate,
    Quote,
    QuoteLineItem,
    QuoteVersion,
    QuoteAttachment,
    PartCategory,
    QuoteStatus,
    QuotePriority,
)

from models.knowledge_preservation import (
    KnowledgeDomain,
    SubjectMatterExpert,
    Interview,
    InterviewTemplate,
    SOPTemplate,
    SOP,
    SOPReviewComment,
    SOPVersion,
    SOPAttachment,
    KnowledgeDomainCategory,
    InterviewStatus,
    SOPStatus,
    SOPPriority,
)

from models.erp_copilot import (
    ERPConfiguration,
    ERPDocument,
    ERPDocumentChunk,
    ERPQuery,
    ERPQueryTemplate,
    DocumentationGap,
    ERPUsageAnalytics,
    ERPSystem,
    DocumentType,
    QueryCategory,
)

from models.manufacturing_costs import (
    WorkCenter,
    LaborRate,
    MaterialCost,
    Routing,
    RoutingOperation,
    OverheadRate,
    CostRollup,
    QuoteCostEstimate,
    CostType,
    LaborType,
    MachineType,
)

__all__ = [
    # Tenant
    "Tenant",
    "TenantSubscription",
    "TenantAPIKey",
    "UsageRecord",
    "SubscriptionTier",
    "SubscriptionStatus",
    "ServiceType",
    # User
    "User",
    "UserSession",
    "AuditLog",
    "UserRole",
    "SystemRole",
    "ROLE_PERMISSIONS",
    # Quote Intelligence
    "Part",
    "PartSimilarity",
    "Customer",
    "QuoteTemplate",
    "Quote",
    "QuoteLineItem",
    "QuoteVersion",
    "QuoteAttachment",
    "PartCategory",
    "QuoteStatus",
    "QuotePriority",
    # Knowledge Preservation
    "KnowledgeDomain",
    "SubjectMatterExpert",
    "Interview",
    "InterviewTemplate",
    "SOPTemplate",
    "SOP",
    "SOPReviewComment",
    "SOPVersion",
    "SOPAttachment",
    "KnowledgeDomainCategory",
    "InterviewStatus",
    "SOPStatus",
    "SOPPriority",
    # ERP Copilot
    "ERPConfiguration",
    "ERPDocument",
    "ERPDocumentChunk",
    "ERPQuery",
    "ERPQueryTemplate",
    "DocumentationGap",
    "ERPUsageAnalytics",
    "ERPSystem",
    "DocumentType",
    "QueryCategory",
    # Manufacturing Costs
    "WorkCenter",
    "LaborRate",
    "MaterialCost",
    "Routing",
    "RoutingOperation",
    "OverheadRate",
    "CostRollup",
    "QuoteCostEstimate",
    "CostType",
    "LaborType",
    "MachineType",
]
