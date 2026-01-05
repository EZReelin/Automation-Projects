"""
Structured logging configuration for the Manufacturing Consulting System.

Uses structlog for consistent, machine-parseable log output.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor

from config.settings import settings


def setup_logging() -> None:
    """
    Configure structured logging for the application.
    
    Sets up structlog with appropriate processors based on environment.
    """
    # Common processors
    shared_processors: list[Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if settings.log_format == "json":
        # Production: JSON output
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


class RequestLogger:
    """
    Middleware-style request logging for FastAPI.
    
    Logs request/response details with structured data.
    """
    
    def __init__(self):
        self.logger = get_logger("request")
    
    def log_request(
        self,
        method: str,
        path: str,
        user_id: str | None = None,
        tenant_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Log incoming request."""
        self.logger.info(
            "request_received",
            method=method,
            path=path,
            user_id=user_id,
            tenant_id=tenant_id,
            **(extra or {}),
        )
    
    def log_response(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        user_id: str | None = None,
        tenant_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Log outgoing response."""
        log_method = self.logger.info if status_code < 400 else self.logger.warning
        log_method(
            "request_completed",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=round(duration_ms, 2),
            user_id=user_id,
            tenant_id=tenant_id,
            **(extra or {}),
        )


class AuditLogger:
    """
    Audit logging for security-sensitive operations.
    
    Logs to a separate audit trail for compliance.
    """
    
    def __init__(self):
        self.logger = get_logger("audit")
    
    def log_action(
        self,
        action: str,
        user_id: str | None,
        tenant_id: str | None,
        resource_type: str,
        resource_id: str | None = None,
        old_values: dict | None = None,
        new_values: dict | None = None,
        ip_address: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """
        Log an auditable action.
        
        Args:
            action: Action type (create, update, delete, etc.)
            user_id: Acting user ID
            tenant_id: Tenant context
            resource_type: Type of resource affected
            resource_id: ID of affected resource
            old_values: Previous values (for updates)
            new_values: New values (for creates/updates)
            ip_address: Client IP address
            metadata: Additional context
        """
        self.logger.info(
            "audit_event",
            action=action,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            metadata=metadata,
        )
    
    def log_login(
        self,
        user_id: str,
        success: bool,
        ip_address: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Log authentication attempt."""
        level = self.logger.info if success else self.logger.warning
        level(
            "authentication_attempt",
            user_id=user_id,
            success=success,
            ip_address=ip_address,
            reason=reason,
        )
    
    def log_permission_denied(
        self,
        user_id: str,
        tenant_id: str | None,
        resource_type: str,
        action: str,
        ip_address: str | None = None,
    ) -> None:
        """Log permission denied event."""
        self.logger.warning(
            "permission_denied",
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            action=action,
            ip_address=ip_address,
        )


class ServiceLogger:
    """
    Service-level logging for business operations.
    
    Provides consistent logging across service modules.
    """
    
    def __init__(self, service_name: str):
        self.logger = get_logger(f"service.{service_name}")
        self.service_name = service_name
    
    def log_operation_start(
        self,
        operation: str,
        tenant_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Log start of a business operation."""
        self.logger.info(
            f"{operation}_started",
            service=self.service_name,
            tenant_id=tenant_id,
            **kwargs,
        )
    
    def log_operation_complete(
        self,
        operation: str,
        tenant_id: str | None = None,
        duration_ms: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Log successful completion of an operation."""
        self.logger.info(
            f"{operation}_completed",
            service=self.service_name,
            tenant_id=tenant_id,
            duration_ms=round(duration_ms, 2) if duration_ms else None,
            **kwargs,
        )
    
    def log_operation_failed(
        self,
        operation: str,
        error: Exception,
        tenant_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Log failed operation with error details."""
        self.logger.error(
            f"{operation}_failed",
            service=self.service_name,
            tenant_id=tenant_id,
            error_type=type(error).__name__,
            error_message=str(error),
            **kwargs,
        )


# Global logger instances
request_logger = RequestLogger()
audit_logger = AuditLogger()
