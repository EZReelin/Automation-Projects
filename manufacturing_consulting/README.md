# Manufacturing Consulting System

AI-powered platform for manufacturing consulting services, providing three interconnected service offerings:

1. **Quote Intelligence System** - Parts matching, automated quote generation, historical quote lookup
2. **Knowledge Preservation Package** - Interview-to-SOP pipeline for capturing retiring employee knowledge
3. **ERP Copilot** - Natural language interface for ERP documentation

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Manufacturing Consulting System                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │    Quote     │    │  Knowledge   │    │     ERP      │                   │
│  │ Intelligence │    │ Preservation │    │   Copilot    │                   │
│  │   System     │    │   Package    │    │              │                   │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                   │
│         │                   │                   │                            │
│         ▼                   ▼                   ▼                            │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        Shared Services Layer                           │ │
│  │  • AI Client (Claude/OpenAI)  • Vector Search  • Authentication       │ │
│  │  • Multi-tenant Context       • Logging        • Security             │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│         │                                                                    │
│         ▼                                                                    │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         PostgreSQL Database                            │ │
│  │  • Tenants & Users  • Quotes & Parts  • SOPs & Interviews  • ERP Docs │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Features

### Quote Intelligence System ($8,000-$15,000 + $500-$1,000/month)
- **Parts Matching**: Fuzzy matching with manufacturing nomenclature support
- **AI Quote Generation**: Generate quotes from natural language requests
- **Historical Lookup**: Search and analyze past quotes by part, customer, date
- **Version Control**: Track quote iterations and changes
- **Pricing Intelligence**: AI-assisted pricing recommendations
- **Manufacturing Cost Calculation**: Full cost breakdown with machine hours, labor rates, and overhead
- **Universal Data Import**: Import from any ERP system via CSV, Excel, JSON, or XML

### Knowledge Preservation Package ($3,000-$5,000 per domain)
- **Interview Management**: Schedule and track SME interviews
- **AI Transcription Processing**: Extract procedures from interview transcripts
- **SOP Generation**: Automatically generate structured SOPs from interviews
- **Review Workflow**: Multi-stage approval process
- **Multi-format Export**: PDF, Word, Markdown, HTML

### ERP Copilot ($2,500-$5,000 + $300-$500/month)
- **Natural Language Queries**: Ask questions in plain English
- **Documentation Indexing**: Semantic search across ERP docs
- **Context-Aware Responses**: Answers reference specific documentation
- **Gap Identification**: Track unanswered questions for doc improvements
- **Usage Analytics**: Monitor adoption and common queries

## Universal ERP Integration

The system is designed to work with **any ERP system** used in manufacturing. Rather than requiring expensive, proprietary integrations, we use a flexible approach:

### Supported Integration Methods

| Method | Best For | Complexity |
|--------|----------|------------|
| **File Import** (CSV, Excel, JSON, XML) | Any ERP | Low |
| **REST API** | Modern ERPs with APIs | Medium |
| **OData** | Microsoft Dynamics, SAP | Medium |
| **Database Direct** (ODBC) | Legacy systems | High |

### Pre-Built Mappings Available For

- SAP (S/4HANA, Business One, ECC)
- Oracle (NetSuite, JD Edwards, E-Business Suite)
- Microsoft Dynamics (365, NAV, GP)
- Epicor (Prophet 21, Kinetic)
- SYSPRO
- Infor (CloudSuite, SyteLine, VISUAL)
- Sage (100, 300, X3)
- JobBOSS
- E2 Shop System
- Global Shop Solutions
- ECi M1
- Plex
- IQMS/DELMIAworks
- **Any system with CSV/Excel export** (Generic mappings)

### Import Workflow

1. Export data from your ERP (parts, routings, costs, customers)
2. Use `/api/v1/imports/validate` to preview and map fields
3. Import with automatic field detection
4. System suggests mappings based on detected columns

## Manufacturing Cost Calculation

The system includes comprehensive manufacturing cost support for accurate quoting:

### Cost Components

| Component | Description | Source |
|-----------|-------------|--------|
| **Material Costs** | Raw materials with scrap factors | Material cost tables |
| **Machine Hours** | Equipment time at hourly rates | Routings + Work centers |
| **Labor Hours** | Setup + run time by skill level | Routings + Labor rates |
| **Overhead** | Burden allocation | Overhead rates |
| **Outside Processing** | Subcontract operations | Routing operations |
| **Tooling** | Fixtures and consumable tooling | Routing operations |

### Work Center Rates

Define hourly rates for each machine/work center:
- Machine rate per hour (depreciation, maintenance, utilities)
- Labor rate per hour (operator wages)
- Overhead rate per hour (facility, supervision)

### Labor Rate Management

Track labor costs by skill classification:
- Unskilled, Semi-skilled, Skilled, Technician, Engineer
- Base rate + burden (benefits, insurance)
- Overtime multipliers

### Routing-Based Costing

Import or define manufacturing routings with:
- Operation sequence and work center assignments
- Setup time and run time per piece
- Outside processing costs
- Tooling and fixture costs

### API Endpoints

```bash
# Calculate cost for a part
POST /api/v1/costs/calculate
{
  "part_id": "...",
  "quantity": 100
}

# Import work centers with rates
POST /api/v1/imports/work-centers

# Import labor rates
POST /api/v1/imports/labor-rates

# Import routings
POST /api/v1/imports/routings
```

## Technology Stack

- **Backend**: Python 3.11+, FastAPI
- **Database**: PostgreSQL with async support (asyncpg)
- **ORM**: SQLAlchemy 2.0 with async sessions
- **AI**: Anthropic Claude API, OpenAI Embeddings
- **Vector Search**: In-memory (production: ChromaDB/pgvector)
- **Authentication**: JWT with refresh tokens
- **Task Queue**: Celery with Redis (for async processing)

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis (optional, for task queue)

### Installation

```bash
# Clone repository
cd manufacturing_consulting

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp config/.env.example .env
# Edit .env with your configuration

# Run database migrations
alembic upgrade head

# Start the server
python main.py
```

### Configuration

Key environment variables:

```env
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=manufacturing_consulting
DB_USER=postgres
DB_PASSWORD=your_password

# AI APIs
AI_ANTHROPIC_API_KEY=your_anthropic_key
AI_OPENAI_API_KEY=your_openai_key

# Authentication
AUTH_SECRET_KEY=your-super-secret-key-min-32-chars
```

## API Documentation

When running in development mode, API documentation is available at:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

### Authentication

All endpoints (except `/api/v1/auth/login`) require JWT authentication:

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=user@example.com&password=yourpassword"

# Use token
curl http://localhost:8000/api/v1/quotes \
  -H "Authorization: Bearer <access_token>"
```

## Project Structure

```
manufacturing_consulting/
├── api/
│   ├── routes/           # API endpoint handlers
│   │   ├── auth.py       # Authentication endpoints
│   │   ├── quotes.py     # Quote Intelligence endpoints
│   │   ├── knowledge.py  # Knowledge Preservation endpoints
│   │   ├── erp.py        # ERP Copilot endpoints
│   │   ├── tenants.py    # Tenant management
│   │   ├── admin.py      # Admin dashboard
│   │   ├── imports.py    # Universal data import endpoints
│   │   └── costs.py      # Manufacturing cost endpoints
│   └── dependencies.py   # FastAPI dependencies
├── config/
│   ├── settings.py       # Configuration management
│   └── .env.example      # Example environment file
├── database/
│   └── base.py           # Database connection and sessions
├── models/
│   ├── tenant.py         # Tenant and subscription models
│   ├── user.py           # User and authentication models
│   ├── quote_intelligence.py  # Quote system models
│   ├── knowledge_preservation.py  # SOP system models
│   ├── erp_copilot.py    # ERP system models
│   └── manufacturing_costs.py  # Work centers, routings, cost models
├── services/
│   ├── auth_service.py   # Authentication service
│   ├── quote_intelligence/   # Quote services
│   │   ├── parts_service.py
│   │   ├── quote_service.py
│   │   ├── matching_service.py
│   │   ├── pricing_service.py
│   │   └── cost_calculation_service.py  # Manufacturing cost calculations
│   ├── knowledge_preservation/  # Knowledge services
│   ├── erp_copilot/      # ERP services
│   └── integrations/     # Universal ERP integration
│       ├── erp_connector.py    # Connection handlers
│       ├── data_import.py      # Parts/customer import
│       └── cost_import.py      # Work centers/routings import
├── schemas/
│   └── __init__.py       # Pydantic schemas
├── utils/
│   ├── ai_client.py      # AI API wrapper
│   ├── vector_search.py  # Semantic search
│   ├── security.py       # Security utilities
│   └── logging.py        # Logging configuration
├── main.py               # Application entry point
└── requirements.txt      # Python dependencies
```

## Multi-Tenant Architecture

The system supports complete data isolation between clients:

- Each tenant has its own set of users, quotes, SOPs, and ERP configurations
- Tenant context is automatically determined from authenticated user
- System administrators can access multiple tenants
- Usage tracking per tenant for billing

## Service Subscription Model

Tenants can subscribe to services independently:

| Service | Implementation Fee | Monthly Retainer |
|---------|-------------------|------------------|
| Quote Intelligence | $8,000-$15,000 | $500-$1,000 |
| Knowledge Preservation | $3,000-$5,000 per domain | - |
| ERP Copilot | $2,500-$5,000 | $300-$500 |

## Client Onboarding Workflow

### Quote Intelligence System
1. Initial consultation and requirements gathering
2. **ERP Data Export**: Client exports data from their existing system
3. **Parts & Customer Import**: Upload CSV/Excel files via `/api/v1/imports/parts` and `/api/v1/imports/customers`
4. **Work Center Setup**: Import machine/work center definitions with hourly rates
5. **Labor Rates**: Configure labor rates by skill classification
6. **Routing Import**: Import manufacturing routings from ERP or create manually
7. **Cost Validation**: Verify cost calculations against known parts
8. Template customization
9. User training

### Knowledge Preservation Package
1. Identify knowledge domains
2. Select subject matter experts
3. Schedule interview sessions
4. Record and transcribe interviews
5. Generate and review SOPs
6. Approval and publishing

### ERP Copilot
1. ERP system configuration
2. Documentation collection
3. Document ingestion and indexing
4. Custom terminology mapping
5. Query template creation
6. User rollout

## Security Considerations

- **Authentication**: JWT tokens with short-lived access tokens and refresh rotation
- **Authorization**: Role-based access control (RBAC) with granular permissions
- **Data Isolation**: Strict tenant separation at query level
- **Encryption**: Passwords hashed with bcrypt, sensitive data encrypted at rest
- **Audit Logging**: All significant actions logged for compliance
- **Rate Limiting**: API rate limiting to prevent abuse

## Monitoring & Metrics

Key metrics to track:

- **Quote Intelligence**: Quotes generated, conversion rate, pricing accuracy
- **Knowledge Preservation**: Interviews completed, SOPs published, time savings
- **ERP Copilot**: Query success rate, response time, user satisfaction

## Development

### Running Tests

```bash
pytest tests/ -v --cov=.
```

### Code Quality

```bash
# Format code
black .
isort .

# Lint
ruff check .

# Type checking
mypy .
```

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Production Checklist

- [ ] Set `DEBUG=false` and `ENVIRONMENT=production`
- [ ] Use strong `AUTH_SECRET_KEY`
- [ ] Configure proper database credentials
- [ ] Set up SSL/TLS termination
- [ ] Configure CORS origins
- [ ] Set up log aggregation
- [ ] Configure error tracking (Sentry)
- [ ] Set up database backups
- [ ] Configure rate limiting

## Support

For questions or issues, contact the development team.

## License

Proprietary - All rights reserved.
