"""
FastAPI dependencies for authentication, database, and tenant context.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Header, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from database.base import get_session, TenantContext
from services.auth_service import AuthService
from models.user import User, UserRole
from models.tenant import ServiceType

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db() -> AsyncSession:
    """Get database session dependency."""
    async for session in get_session():
        yield session


DatabaseDep = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DatabaseDep,
) -> dict:
    """
    Get current authenticated user from token.
    
    Raises:
        HTTPException: If token is invalid or user not found
    """
    auth_service = AuthService(db)
    
    payload = await auth_service.validate_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return payload


CurrentUserDep = Annotated[dict, Depends(get_current_user)]


async def get_tenant_id(
    current_user: CurrentUserDep,
    x_tenant_id: str | None = Header(None),
) -> str:
    """
    Get current tenant ID from user or header.
    
    System users can override tenant via header.
    Regular users are scoped to their tenant.
    """
    # System users can specify tenant via header
    if current_user.get("system_role") and x_tenant_id:
        return x_tenant_id
    
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tenant context available",
        )
    
    # Set tenant context for queries
    TenantContext.set_tenant(tenant_id)
    
    return tenant_id


TenantDep = Annotated[str, Depends(get_tenant_id)]


def require_permission(permission: str):
    """
    Factory for permission checking dependency.
    
    Usage:
        @router.get("/items", dependencies=[Depends(require_permission("items.view"))])
    """
    async def check_permission(
        current_user: CurrentUserDep,
        tenant_id: TenantDep,
        db: DatabaseDep,
    ) -> None:
        auth_service = AuthService(db)
        
        has_permission = await auth_service.check_permission(
            current_user["sub"],
            permission,
            tenant_id,
        )
        
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission}",
            )
    
    return check_permission


def require_role(min_role: UserRole):
    """
    Factory for role checking dependency.
    
    Usage:
        @router.get("/admin", dependencies=[Depends(require_role(UserRole.ADMIN))])
    """
    role_hierarchy = {
        UserRole.VIEWER: 0,
        UserRole.ANALYST: 1,
        UserRole.MANAGER: 2,
        UserRole.ADMIN: 3,
        UserRole.OWNER: 4,
    }
    
    async def check_role(current_user: CurrentUserDep) -> None:
        user_role = UserRole(current_user.get("role", "viewer"))
        
        if role_hierarchy.get(user_role, 0) < role_hierarchy.get(min_role, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {min_role.value} or higher required",
            )
    
    return check_role


def require_service(service_type: ServiceType):
    """
    Factory for service subscription checking dependency.
    
    Usage:
        @router.get("/quotes", dependencies=[Depends(require_service(ServiceType.QUOTE_INTELLIGENCE))])
    """
    async def check_service(
        tenant_id: TenantDep,
        db: DatabaseDep,
    ) -> None:
        auth_service = AuthService(db)
        
        has_access = await auth_service.check_service_access(tenant_id, service_type)
        
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Service {service_type.value} not available for this tenant",
            )
    
    return check_service


def require_system_role():
    """Require user to be a system administrator."""
    async def check_system_role(current_user: CurrentUserDep) -> None:
        if not current_user.get("system_role"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="System administrator access required",
            )
    
    return check_system_role


SystemAdminDep = Annotated[None, Depends(require_system_role())]
