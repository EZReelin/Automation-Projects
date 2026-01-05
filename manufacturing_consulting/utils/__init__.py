"""
Utility modules for the Manufacturing Consulting System.

Provides shared functionality across all services:
- AI client for Claude/OpenAI integration
- Vector search for semantic retrieval
- Security utilities for auth and encryption
- Logging utilities for structured logging
"""

from utils.ai_client import ai_client, prompt_builder, AIClient, AIPromptBuilder
from utils.vector_search import (
    VectorStore,
    TenantVectorStore,
    TextChunker,
    SearchResult,
    tenant_vector_store,
    text_chunker,
)
from utils.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    verify_api_key,
    validate_password_strength,
    generate_secure_token,
    mask_sensitive_data,
    RateLimiter,
    rate_limiter,
)
from utils.logging import (
    setup_logging,
    get_logger,
    RequestLogger,
    AuditLogger,
    ServiceLogger,
    request_logger,
    audit_logger,
)

__all__ = [
    # AI Client
    "ai_client",
    "prompt_builder",
    "AIClient",
    "AIPromptBuilder",
    # Vector Search
    "VectorStore",
    "TenantVectorStore",
    "TextChunker",
    "SearchResult",
    "tenant_vector_store",
    "text_chunker",
    # Security
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "generate_api_key",
    "verify_api_key",
    "validate_password_strength",
    "generate_secure_token",
    "mask_sensitive_data",
    "RateLimiter",
    "rate_limiter",
    # Logging
    "setup_logging",
    "get_logger",
    "RequestLogger",
    "AuditLogger",
    "ServiceLogger",
    "request_logger",
    "audit_logger",
]
