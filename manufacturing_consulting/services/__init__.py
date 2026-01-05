"""
Services module for the Manufacturing Consulting System.

Contains business logic for all three service offerings:
- Quote Intelligence System
- Knowledge Preservation Package
- ERP Copilot
"""

from services.auth_service import AuthService

__all__ = ["AuthService"]
