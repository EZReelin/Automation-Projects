"""
Manufacturing Consulting System - Main Application

FastAPI application serving three AI-powered services:
- Quote Intelligence System
- Knowledge Preservation Package  
- ERP Copilot
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from config.settings import settings
from database.base import init_db, close_db
from utils.logging import setup_logging, request_logger, get_logger

# Import routers
from api.routes import auth, quotes, knowledge, erp, admin, tenants

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    setup_logging()
    logger.info("Starting Manufacturing Consulting System", version=settings.app_version)
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Manufacturing Consulting System")
    await close_db()


app = FastAPI(
    title=settings.app_name,
    description="""
## Manufacturing Consulting System API

AI-powered platform for manufacturing consulting services.

### Services

- **Quote Intelligence System**: Parts matching, automated quote generation, historical quote lookup
- **Knowledge Preservation Package**: Interview-to-SOP pipeline, knowledge domain management
- **ERP Copilot**: Natural language interface for ERP documentation

### Authentication

All endpoints (except auth) require a valid JWT token.
Include the token in the Authorization header: `Bearer <token>`

### Multi-Tenant Architecture

This system supports multiple client tenants with isolated data.
Tenant context is determined by the authenticated user.
    """,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing."""
    start_time = time.time()
    
    # Extract user info if available
    user_id = None
    tenant_id = None
    
    request_logger.log_request(
        method=request.method,
        path=request.url.path,
        user_id=user_id,
        tenant_id=tenant_id,
    )
    
    response = await call_next(request)
    
    duration_ms = (time.time() - start_time) * 1000
    
    request_logger.log_response(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
        user_id=user_id,
        tenant_id=tenant_id,
    )
    
    return response


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed messages."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.error(
        "Unhandled exception",
        error_type=type(exc).__name__,
        error_message=str(exc),
        path=request.url.path,
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected error occurred",
        },
    )


# Include routers
app.include_router(auth.router, prefix=f"{settings.api_prefix}/auth", tags=["Authentication"])
app.include_router(quotes.router, prefix=f"{settings.api_prefix}/quotes", tags=["Quote Intelligence"])
app.include_router(knowledge.router, prefix=f"{settings.api_prefix}/knowledge", tags=["Knowledge Preservation"])
app.include_router(erp.router, prefix=f"{settings.api_prefix}/erp", tags=["ERP Copilot"])
app.include_router(tenants.router, prefix=f"{settings.api_prefix}/tenants", tags=["Tenant Management"])
app.include_router(admin.router, prefix=f"{settings.api_prefix}/admin", tags=["Admin Dashboard"])


# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.environment,
    }


@app.get("/", tags=["System"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/api/docs" if settings.debug else "Disabled in production",
        "services": [
            "Quote Intelligence System",
            "Knowledge Preservation Package",
            "ERP Copilot",
        ],
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=settings.workers if not settings.debug else 1,
    )
