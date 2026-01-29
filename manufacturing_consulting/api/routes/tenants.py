"""
Tenant management API routes.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from api.dependencies import DatabaseDep, CurrentUserDep, require_system_role
from models.tenant import Tenant, TenantSubscription, SubscriptionTier, SubscriptionStatus, ServiceType
from models.user import User, UserRole

router = APIRouter()


# Schemas
class TenantCreate(BaseModel):
    name: str
    slug: str
    primary_contact_name: str | None = None
    primary_contact_email: EmailStr | None = None
    industry: str | None = None


class TenantUpdate(BaseModel):
    name: str | None = None
    primary_contact_name: str | None = None
    primary_contact_email: EmailStr | None = None
    industry: str | None = None


class SubscriptionCreate(BaseModel):
    service_type: ServiceType
    tier: SubscriptionTier = SubscriptionTier.STARTER
    monthly_price: float = 0
    implementation_fee: float = 0


class UserInvite(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    role: UserRole = UserRole.VIEWER


# Tenant endpoints (system admin only)
@router.get("/", dependencies=[Depends(require_system_role())])
async def list_tenants(
    db: DatabaseDep,
    current_user: CurrentUserDep,
    is_active: bool = True,
    limit: int = Query(50, le=100),
    offset: int = 0,
):
    """List all tenants (system admin only)."""
    from sqlalchemy import func
    
    conditions = [Tenant.is_active == is_active]
    
    count_result = await db.execute(
        select(func.count(Tenant.id)).where(and_(*conditions))
    )
    total = count_result.scalar_one()
    
    result = await db.execute(
        select(Tenant)
        .where(and_(*conditions))
        .order_by(Tenant.name)
        .limit(limit)
        .offset(offset)
    )
    tenants = result.scalars().all()
    
    return {
        "items": [
            {
                "id": t.id,
                "name": t.name,
                "slug": t.slug,
                "industry": t.industry,
                "onboarding_completed": t.onboarding_completed,
                "created_at": t.created_at.isoformat(),
            }
            for t in tenants
        ],
        "total": total,
    }


@router.post("/", dependencies=[Depends(require_system_role())])
async def create_tenant(
    body: TenantCreate,
    db: DatabaseDep,
    current_user: CurrentUserDep,
):
    """Create a new tenant (system admin only)."""
    # Check for existing slug
    existing = await db.execute(
        select(Tenant).where(Tenant.slug == body.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Slug already exists")
    
    tenant = Tenant(
        id=str(uuid4()),
        name=body.name,
        slug=body.slug,
        primary_contact_name=body.primary_contact_name,
        primary_contact_email=body.primary_contact_email,
        industry=body.industry,
    )
    
    db.add(tenant)
    await db.flush()
    
    return {"id": tenant.id, "slug": tenant.slug}


@router.get("/{tenant_id}", dependencies=[Depends(require_system_role())])
async def get_tenant(
    tenant_id: str,
    db: DatabaseDep,
    current_user: CurrentUserDep,
):
    """Get tenant details (system admin only)."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Get subscriptions
    subs_result = await db.execute(
        select(TenantSubscription).where(TenantSubscription.tenant_id == tenant_id)
    )
    subscriptions = subs_result.scalars().all()
    
    # Get user count
    from sqlalchemy import func
    users_result = await db.execute(
        select(func.count(User.id)).where(User.tenant_id == tenant_id)
    )
    user_count = users_result.scalar_one()
    
    return {
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "primary_contact_name": tenant.primary_contact_name,
        "primary_contact_email": tenant.primary_contact_email,
        "industry": tenant.industry,
        "is_active": tenant.is_active,
        "onboarding_completed": tenant.onboarding_completed,
        "created_at": tenant.created_at.isoformat(),
        "subscriptions": [
            {
                "id": s.id,
                "service_type": s.service_type.value,
                "tier": s.tier.value,
                "status": s.status.value,
                "monthly_price": float(s.monthly_price),
            }
            for s in subscriptions
        ],
        "user_count": user_count,
    }


@router.patch("/{tenant_id}", dependencies=[Depends(require_system_role())])
async def update_tenant(
    tenant_id: str,
    body: TenantUpdate,
    db: DatabaseDep,
    current_user: CurrentUserDep,
):
    """Update tenant (system admin only)."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(tenant, key, value)
    
    tenant.updated_at = datetime.utcnow()
    await db.flush()
    
    return {"id": tenant.id}


# Subscriptions
@router.post("/{tenant_id}/subscriptions", dependencies=[Depends(require_system_role())])
async def add_subscription(
    tenant_id: str,
    body: SubscriptionCreate,
    db: DatabaseDep,
    current_user: CurrentUserDep,
):
    """Add a service subscription to tenant."""
    # Verify tenant exists
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    if not tenant_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Check for existing subscription
    existing = await db.execute(
        select(TenantSubscription).where(
            and_(
                TenantSubscription.tenant_id == tenant_id,
                TenantSubscription.service_type == body.service_type,
                TenantSubscription.status != SubscriptionStatus.CANCELLED,
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Subscription already exists")
    
    subscription = TenantSubscription(
        id=str(uuid4()),
        tenant_id=tenant_id,
        service_type=body.service_type,
        tier=body.tier,
        monthly_price=body.monthly_price,
        implementation_fee=body.implementation_fee,
        status=SubscriptionStatus.ACTIVE,
    )
    
    db.add(subscription)
    await db.flush()
    
    return {"id": subscription.id, "service_type": subscription.service_type.value}


@router.delete("/{tenant_id}/subscriptions/{subscription_id}", dependencies=[Depends(require_system_role())])
async def cancel_subscription(
    tenant_id: str,
    subscription_id: str,
    db: DatabaseDep,
    current_user: CurrentUserDep,
):
    """Cancel a subscription."""
    result = await db.execute(
        select(TenantSubscription).where(
            and_(
                TenantSubscription.id == subscription_id,
                TenantSubscription.tenant_id == tenant_id,
            )
        )
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    subscription.status = SubscriptionStatus.CANCELLED
    subscription.end_date = datetime.utcnow()
    
    await db.flush()
    
    return {"message": "Subscription cancelled"}


# Users
@router.get("/{tenant_id}/users", dependencies=[Depends(require_system_role())])
async def list_tenant_users(
    tenant_id: str,
    db: DatabaseDep,
    current_user: CurrentUserDep,
    limit: int = Query(50, le=100),
    offset: int = 0,
):
    """List users for a tenant."""
    result = await db.execute(
        select(User)
        .where(User.tenant_id == tenant_id)
        .order_by(User.last_name)
        .limit(limit)
        .offset(offset)
    )
    users = result.scalars().all()
    
    return {
        "items": [
            {
                "id": u.id,
                "email": u.email,
                "name": u.full_name,
                "role": u.role.value,
                "is_active": u.is_active,
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            }
            for u in users
        ]
    }


@router.post("/{tenant_id}/users", dependencies=[Depends(require_system_role())])
async def invite_user_to_tenant(
    tenant_id: str,
    body: UserInvite,
    db: DatabaseDep,
    current_user: CurrentUserDep,
):
    """Invite a new user to a tenant."""
    # Verify tenant exists
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    if not tenant_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Check for existing user
    existing = await db.execute(
        select(User).where(User.email == body.email.lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    from utils.security import get_password_hash, generate_secure_token
    
    # Create user with temporary password
    temp_password = generate_secure_token(16)
    
    user = User(
        id=str(uuid4()),
        email=body.email.lower(),
        hashed_password=get_password_hash(temp_password),
        first_name=body.first_name,
        last_name=body.last_name,
        tenant_id=tenant_id,
        role=body.role,
    )
    
    db.add(user)
    await db.flush()
    
    # In production, send invitation email with temp password
    
    return {
        "id": user.id,
        "email": user.email,
        "temp_password": temp_password,  # Remove in production
    }
