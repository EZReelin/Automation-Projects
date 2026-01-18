"""
FabriGuard API - Main Application Entry Point

AI-powered predictive maintenance platform for metal fabricators.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from api.routers import assets, sensors, alerts, predictions, work_orders, users, auth, dashboard, readings
from api.config import settings
from api.database import init_db

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    # Startup
    logger.info("Starting FabriGuard API", version=settings.VERSION)
    await init_db()
    logger.info("Database initialized")

    yield

    # Shutdown
    logger.info("Shutting down FabriGuard API")


# Create FastAPI application
app = FastAPI(
    title="FabriGuard API",
    description="""
    ## AI-Powered Predictive Maintenance Platform

    FabriGuard helps small-to-medium metal fabrication shops predict equipment
    failures before they occur, reducing unplanned downtime and maintenance costs.

    ### Key Features
    - **Asset Management**: Track and monitor your equipment fleet
    - **Sensor Integration**: Real-time data collection from IoT sensors
    - **Predictive Analytics**: ML-powered failure predictions and RUL estimates
    - **Smart Alerts**: Actionable notifications with plain-language explanations
    - **Work Orders**: Streamlined maintenance workflow management
    - **ROI Tracking**: Documented cost savings and downtime avoidance

    ### Authentication
    All endpoints require Bearer token authentication. Obtain a token via `/api/v1/auth/login`.
    """,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    logger.error(
        "Unhandled exception",
        error=str(exc),
        path=request.url.path,
        method=request.method
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal error occurred. Please try again later.",
            "error_id": str(id(exc))  # For debugging
        }
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Check API health status."""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "service": "fabriguard-api"
    }


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """API root - returns basic information."""
    return {
        "name": "FabriGuard API",
        "version": settings.VERSION,
        "description": "AI-powered predictive maintenance platform for metal fabricators",
        "docs": "/docs",
        "health": "/health"
    }


# Include API routers
API_PREFIX = "/api/v1"

app.include_router(
    auth.router,
    prefix=f"{API_PREFIX}/auth",
    tags=["Authentication"]
)

app.include_router(
    users.router,
    prefix=f"{API_PREFIX}/users",
    tags=["Users"]
)

app.include_router(
    assets.router,
    prefix=f"{API_PREFIX}/assets",
    tags=["Assets"]
)

app.include_router(
    sensors.router,
    prefix=f"{API_PREFIX}/sensors",
    tags=["Sensors"]
)

app.include_router(
    readings.router,
    prefix=f"{API_PREFIX}/readings",
    tags=["Sensor Readings"]
)

app.include_router(
    alerts.router,
    prefix=f"{API_PREFIX}/alerts",
    tags=["Alerts"]
)

app.include_router(
    predictions.router,
    prefix=f"{API_PREFIX}/predictions",
    tags=["Predictions"]
)

app.include_router(
    work_orders.router,
    prefix=f"{API_PREFIX}/work-orders",
    tags=["Work Orders"]
)

app.include_router(
    dashboard.router,
    prefix=f"{API_PREFIX}/dashboard",
    tags=["Dashboard"]
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
