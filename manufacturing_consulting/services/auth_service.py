"""
Authentication and authorization service.

Handles user authentication, session management, and tenant context.
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User, UserSession, UserRole, SystemRole
from models.tenant import Tenant, TenantSubscription, ServiceType
from utils.security import (
    verify_password, get_password_hash, create_access_token,
    create_refresh_token, decode_token, validate_password_strength,
    generate_secure_token,
)
from utils.logging import ServiceLogger, audit_logger
from config.settings import settings


class AuthService:
    """
    Service for authentication and authorization.
    
    Provides:
    - User authentication
    - Session management
    - Tenant context validation
    - Permission checking
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = ServiceLogger("auth")
    
    async def authenticate(
        self,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Authenticate a user and create session.
        
        Args:
            email: User email
            password: User password
            ip_address: Client IP
            user_agent: Client user agent
            
        Returns:
            Dict with tokens and user info, or None if failed
        """
        self.logger.log_operation_start("authenticate", email=email)
        
        # Get user
        user = await self._get_user_by_email(email)
        if not user:
            audit_logger.log_login(email, success=False, ip_address=ip_address, reason="user_not_found")
            return None
        
        # Check if locked
        if user.locked_until and user.locked_until > datetime.utcnow():
            audit_logger.log_login(user.id, success=False, ip_address=ip_address, reason="account_locked")
            return None
        
        # Verify password
        if not verify_password(password, user.hashed_password):
            user.failed_login_attempts += 1
            
            if user.failed_login_attempts >= settings.auth.max_login_attempts:
                user.locked_until = datetime.utcnow() + timedelta(
                    minutes=settings.auth.lockout_duration_minutes
                )
            
            await self.session.flush()
            
            audit_logger.log_login(user.id, success=False, ip_address=ip_address, reason="invalid_password")
            return None
        
        # Check if active
        if not user.is_active:
            audit_logger.log_login(user.id, success=False, ip_address=ip_address, reason="account_inactive")
            return None
        
        # Reset failed attempts
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.utcnow()
        
        # Create tokens
        token_data = {
            "sub": user.id,
            "email": user.email,
            "tenant_id": user.tenant_id,
            "role": user.role.value,
            "system_role": user.system_role.value if user.system_role else None,
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        
        # Create session
        session = UserSession(
            id=str(uuid4()),
            user_id=user.id,
            token_hash=get_password_hash(access_token)[:255],
            refresh_token_hash=get_password_hash(refresh_token)[:255],
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.utcnow() + timedelta(minutes=settings.auth.access_token_expire_minutes),
        )
        
        self.session.add(session)
        await self.session.flush()
        
        audit_logger.log_login(user.id, success=True, ip_address=ip_address)
        
        self.logger.log_operation_complete("authenticate", user_id=user.id)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.auth.access_token_expire_minutes * 60,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.full_name,
                "tenant_id": user.tenant_id,
                "role": user.role.value,
                "system_role": user.system_role.value if user.system_role else None,
            },
        }
    
    async def refresh_tokens(
        self,
        refresh_token: str,
        ip_address: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: Refresh token
            ip_address: Client IP
            
        Returns:
            New tokens or None if invalid
        """
        # Decode token
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None
        
        user_id = payload.get("sub")
        
        # Verify session exists and isn't revoked
        session_result = await self.session.execute(
            select(UserSession).where(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.is_revoked == False,
                )
            ).order_by(UserSession.created_at.desc()).limit(1)
        )
        user_session = session_result.scalar_one_or_none()
        
        if not user_session:
            return None
        
        # Get user
        user = await self._get_user_by_id(user_id)
        if not user or not user.is_active:
            return None
        
        # Create new tokens
        token_data = {
            "sub": user.id,
            "email": user.email,
            "tenant_id": user.tenant_id,
            "role": user.role.value,
            "system_role": user.system_role.value if user.system_role else None,
        }
        
        new_access_token = create_access_token(token_data)
        new_refresh_token = create_refresh_token(token_data)
        
        # Update session
        user_session.token_hash = get_password_hash(new_access_token)[:255]
        user_session.refresh_token_hash = get_password_hash(new_refresh_token)[:255]
        user_session.expires_at = datetime.utcnow() + timedelta(minutes=settings.auth.access_token_expire_minutes)
        user_session.last_activity_at = datetime.utcnow()
        user_session.ip_address = ip_address
        
        await self.session.flush()
        
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": settings.auth.access_token_expire_minutes * 60,
        }
    
    async def logout(
        self,
        user_id: str,
        session_id: str | None = None,
        all_sessions: bool = False,
    ) -> bool:
        """
        Logout user by revoking session(s).
        
        Args:
            user_id: User ID
            session_id: Specific session to revoke
            all_sessions: Revoke all sessions
            
        Returns:
            True if successful
        """
        conditions = [
            UserSession.user_id == user_id,
            UserSession.is_revoked == False,
        ]
        
        if session_id and not all_sessions:
            conditions.append(UserSession.id == session_id)
        
        result = await self.session.execute(
            select(UserSession).where(and_(*conditions))
        )
        sessions = result.scalars().all()
        
        for sess in sessions:
            sess.is_revoked = True
            sess.revoked_at = datetime.utcnow()
            sess.revocation_reason = "user_logout"
        
        await self.session.flush()
        
        return True
    
    async def register_user(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        tenant_id: str | None = None,
        role: UserRole = UserRole.VIEWER,
    ) -> User | None:
        """
        Register a new user.
        
        Args:
            email: User email
            password: User password
            first_name: First name
            last_name: Last name
            tenant_id: Tenant to assign to
            role: Initial role
            
        Returns:
            Created User or None if validation fails
        """
        # Validate password
        is_valid, issues = validate_password_strength(password)
        if not is_valid:
            raise ValueError(f"Invalid password: {', '.join(issues)}")
        
        # Check for existing user
        existing = await self._get_user_by_email(email)
        if existing:
            raise ValueError("Email already registered")
        
        # Verify tenant exists if provided
        if tenant_id:
            tenant = await self._get_tenant(tenant_id)
            if not tenant:
                raise ValueError("Tenant not found")
        
        user = User(
            id=str(uuid4()),
            email=email.lower(),
            hashed_password=get_password_hash(password),
            first_name=first_name,
            last_name=last_name,
            tenant_id=tenant_id,
            role=role,
        )
        
        self.session.add(user)
        await self.session.flush()
        
        return user
    
    async def validate_token(self, token: str) -> dict[str, Any] | None:
        """
        Validate an access token and return payload.
        
        Args:
            token: Access token
            
        Returns:
            Token payload or None if invalid
        """
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            return None
        
        # Verify user still exists and is active
        user = await self._get_user_by_id(payload.get("sub"))
        if not user or not user.is_active:
            return None
        
        return payload
    
    async def check_permission(
        self,
        user_id: str,
        permission: str,
        tenant_id: str | None = None,
    ) -> bool:
        """
        Check if user has a specific permission.
        
        Args:
            user_id: User ID
            permission: Permission to check
            tenant_id: Tenant context
            
        Returns:
            True if permitted
        """
        user = await self._get_user_by_id(user_id)
        if not user:
            return False
        
        # System admins have all permissions
        if user.system_role == SystemRole.SUPERADMIN:
            return True
        
        # Check tenant context
        if tenant_id and user.tenant_id != tenant_id:
            # System users can access any tenant
            if not user.system_role:
                return False
        
        return user.has_permission(permission)
    
    async def check_service_access(
        self,
        tenant_id: str,
        service_type: ServiceType,
    ) -> bool:
        """
        Check if tenant has access to a specific service.
        
        Args:
            tenant_id: Tenant ID
            service_type: Service to check
            
        Returns:
            True if tenant has active subscription
        """
        result = await self.session.execute(
            select(TenantSubscription).where(
                and_(
                    TenantSubscription.tenant_id == tenant_id,
                    TenantSubscription.service_type == service_type,
                    TenantSubscription.status.in_(["active", "trial"]),
                )
            )
        )
        subscription = result.scalar_one_or_none()
        
        return subscription is not None
    
    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Change user password."""
        user = await self._get_user_by_id(user_id)
        if not user:
            return False
        
        # Verify current password
        if not verify_password(current_password, user.hashed_password):
            return False
        
        # Validate new password
        is_valid, issues = validate_password_strength(new_password)
        if not is_valid:
            raise ValueError(f"Invalid password: {', '.join(issues)}")
        
        user.hashed_password = get_password_hash(new_password)
        user.password_changed_at = datetime.utcnow()
        
        # Revoke all sessions
        await self.logout(user_id, all_sessions=True)
        
        await self.session.flush()
        
        return True
    
    async def _get_user_by_email(self, email: str) -> User | None:
        """Get user by email."""
        result = await self.session.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()
    
    async def _get_user_by_id(self, user_id: str) -> User | None:
        """Get user by ID."""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def _get_tenant(self, tenant_id: str) -> Tenant | None:
        """Get tenant by ID."""
        result = await self.session.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        return result.scalar_one_or_none()
