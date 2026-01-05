# Manufacturing Consulting System - System Design Document

## Executive Summary

This document describes the architecture and design of the Manufacturing Consulting System, an AI-powered platform serving manufacturing clients with three core services: Quote Intelligence, Knowledge Preservation, and ERP Copilot.

## Design Goals

1. **Modularity**: Services can be purchased independently
2. **Scalability**: Support multiple client deployments
3. **Maintainability**: Clear boundaries and well-documented code
4. **Security**: Enterprise-grade data protection
5. **Reliability**: Production-ready with proper error handling

## High-Level Architecture

```
                                   ┌─────────────────┐
                                   │   Load Balancer │
                                   │    (nginx/ALB)  │
                                   └────────┬────────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    │                       │                       │
              ┌─────▼─────┐          ┌──────▼──────┐         ┌─────▼─────┐
              │  App Pod  │          │  App Pod   │         │  App Pod  │
              │   (API)   │          │   (API)    │         │   (API)   │
              └─────┬─────┘          └──────┬─────┘         └─────┬─────┘
                    │                       │                       │
                    └───────────────────────┼───────────────────────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    │                       │                       │
              ┌─────▼─────┐          ┌──────▼──────┐         ┌─────▼─────┐
              │ PostgreSQL│          │    Redis    │         │   S3/GCS  │
              │ (Primary) │          │   Cluster   │         │  Storage  │
              └───────────┘          └─────────────┘         └───────────┘
```

## Component Design

### 1. API Layer (FastAPI)

**Responsibilities:**
- Request routing and validation
- Authentication and authorization
- Rate limiting
- Response formatting

**Key Design Decisions:**
- Async-first design for high concurrency
- OpenAPI documentation auto-generation
- Dependency injection for testability

### 2. Service Layer

Each service module follows the same pattern:

```python
class ServiceName:
    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.logger = ServiceLogger("service_name")
    
    async def business_operation(self, params) -> Result:
        self.logger.log_operation_start(...)
        # Business logic
        self.logger.log_operation_complete(...)
        return result
```

### 3. Data Layer (SQLAlchemy 2.0)

**Model Hierarchy:**
```
Base
├── Tenant (system-wide)
├── User (system-wide)
└── TenantBase (tenant-scoped)
    ├── Quote, Part, Customer
    ├── SOP, Interview, KnowledgeDomain
    └── ERPDocument, ERPQuery
```

**Tenant Isolation:**
All tenant-specific models inherit from `TenantBase`, which adds:
- `tenant_id` column with index
- Automatic tenant filtering in queries

### 4. AI Integration Layer

**Unified Client:**
```python
class AIClient:
    async def generate_text(prompt, system_prompt, model) -> str
    async def generate_structured(prompt, schema) -> dict
    async def generate_embeddings(texts) -> list[list[float]]
```

**Prompt Templates:**
Centralized prompt management for consistency and easy updates.

## Service Modules

### Quote Intelligence System

```
┌─────────────────────────────────────────────────────────┐
│                 Quote Intelligence                       │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   Parts     │  │   Quote     │  │  Matching   │     │
│  │  Service    │  │  Service    │  │  Service    │     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
│         │                │                │             │
│         └────────────────┼────────────────┘             │
│                          │                              │
│                   ┌──────▼──────┐                       │
│                   │   Pricing   │                       │
│                   │   Service   │                       │
│                   └─────────────┘                       │
└─────────────────────────────────────────────────────────┘
```

**Data Flow:**
1. Customer submits quote request (text or structured)
2. Parts matching identifies catalog items
3. Pricing service calculates recommendations
4. Quote service generates draft
5. Approval workflow for finalization

### Knowledge Preservation Package

```
┌─────────────────────────────────────────────────────────┐
│              Knowledge Preservation                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   Interview      →    Transcript     →    SOP           │
│   Scheduling          Processing          Generation    │
│                                                          │
│   ┌─────────┐       ┌─────────┐       ┌─────────┐       │
│   │Schedule │  ──►  │Transcribe│ ──►  │Generate │       │
│   │Interview│       │& Extract │       │  SOP    │       │
│   └─────────┘       └─────────┘       └─────────┘       │
│                                           │             │
│                                    ┌──────▼──────┐      │
│                                    │   Review    │      │
│                                    │  Workflow   │      │
│                                    └──────┬──────┘      │
│                                           │             │
│                                    ┌──────▼──────┐      │
│                                    │   Export    │      │
│                                    │  (PDF/DOCX) │      │
│                                    └─────────────┘      │
└─────────────────────────────────────────────────────────┘
```

**AI Processing Pipeline:**
1. Raw transcript cleaning
2. Topic extraction
3. Procedure identification
4. Key insight extraction
5. Segment analysis
6. SOP content generation

### ERP Copilot

```
┌─────────────────────────────────────────────────────────┐
│                    ERP Copilot                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   ┌──────────────────────────────────────────────────┐  │
│   │                Document Ingestion                 │  │
│   │  PDF/DOCX ──► Extract ──► Chunk ──► Embed ──► Index│
│   └──────────────────────────────────────────────────┘  │
│                          │                              │
│   ┌──────────────────────▼───────────────────────────┐  │
│   │                  Query Processing                 │  │
│   │                                                   │  │
│   │  Query ──► Classify ──► Search ──► Generate      │  │
│   │              │           │            │           │  │
│   │          Template?   Vector DB    AI Response    │  │
│   └──────────────────────────────────────────────────┘  │
│                          │                              │
│   ┌──────────────────────▼───────────────────────────┐  │
│   │                   Analytics                       │  │
│   │  • Usage tracking  • Gap identification          │  │
│   │  • Performance metrics  • User feedback          │  │
│   └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Security Architecture

### Authentication Flow

```
┌────────┐     ┌─────────┐     ┌──────────┐     ┌─────────┐
│ Client │────►│  Login  │────►│ Validate │────►│ Generate│
│        │     │ Request │     │ Password │     │  Tokens │
└────────┘     └─────────┘     └──────────┘     └────┬────┘
                                                     │
┌────────┐     ┌─────────┐     ┌──────────┐         │
│ Client │◄────│  Token  │◄────│  Create  │◄────────┘
│        │     │ Response│     │  Session │
└────────┘     └─────────┘     └──────────┘
```

### Authorization Model

```
Permission Hierarchy:

Owner
  └── tenant.manage, billing.manage
  └── Admin
        └── users.manage
        └── Manager
              └── quotes.approve, sops.approve
              └── Analyst
                    └── quotes.manage, sops.manage
                    └── Viewer
                          └── *.view, erp.query
```

## Database Schema

### Core Entities

```
tenants ──┬── users
          ├── tenant_subscriptions
          └── usage_records

users ───── user_sessions
        └── audit_logs
```

### Quote Intelligence

```
parts ──┬── part_similarities
        └── quote_line_items
        
quotes ──┬── quote_line_items
         ├── quote_versions
         └── quote_attachments

customers ── quotes
```

### Knowledge Preservation

```
knowledge_domains ──┬── interviews
                    └── sops

subject_matter_experts ── interviews

interviews ── sops (source)

sops ──┬── sop_versions
       ├── sop_review_comments
       └── sop_attachments
```

### ERP Copilot

```
erp_configurations ──┬── erp_documents
                     └── erp_queries

erp_documents ── erp_document_chunks

documentation_gaps (standalone)
erp_usage_analytics (standalone)
```

## Scalability Considerations

### Horizontal Scaling
- Stateless API servers behind load balancer
- Database connection pooling
- Redis for session storage and caching

### Vertical Scaling
- Async processing for I/O-bound operations
- Background task queue for heavy processing
- Batch embedding generation

### Data Partitioning
- Tenant-based logical partitioning
- Time-based partitioning for analytics
- Archive strategy for old quotes/SOPs

## Monitoring & Observability

### Metrics (Prometheus)
- Request latency (p50, p95, p99)
- Error rates by endpoint
- AI API usage and costs
- Database query performance

### Logging (Structlog)
- Structured JSON logging
- Request tracing with correlation IDs
- Audit trail for security events

### Alerting
- High error rates
- Slow response times
- AI API failures
- Database connection issues

## Disaster Recovery

### Backup Strategy
- Daily database backups
- Point-in-time recovery capability
- Document storage redundancy

### Recovery Procedures
1. Database restoration from backup
2. Vector index rebuild from documents
3. Session invalidation and re-authentication

## Future Considerations

### Planned Enhancements
- Real-time collaboration on quotes
- Voice interface for ERP queries
- Mobile application
- Integration marketplace

### Technical Debt
- Migration to pgvector for vector search
- GraphQL API option
- Kubernetes deployment manifests
