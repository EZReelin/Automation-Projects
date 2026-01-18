"""
Users Router

Manages user accounts within an organization.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import uuid

from api.database import get_db
from api.routers.auth import get_current_active_user, require_role, get_password_hash
from models.user import User, UserRole

router = APIRouter()


# Pydantic Models
class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = None
    job_title: Optional[str] = None
    notify_email: Optional[bool] = None
    notify_sms: Optional[bool] = None
    notify_push: Optional[bool] = None
    alert_threshold: Optional[str] = None


class UserRoleUpdate(BaseModel):
    role: UserRole


class UserStatusUpdate(BaseModel):
    is_active: bool


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    phone: Optional[str]
    job_title: Optional[str]
    organization_id: uuid.UUID
    role: UserRole
    is_active: bool
    is_email_verified: bool
    notify_email: bool
    notify_sms: bool
    notify_push: bool
    alert_threshold: str
    last_login_at: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    items: List[UserResponse]
    total: int


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class DeviceToken(BaseModel):
    device_token: str
    device_platform: str = Field(..., pattern="^(ios|android)$")


# Routes
@router.get("", response_model=UserListResponse)
async def list_users(
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_role(UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    """List users in the organization. Requires Manager role."""
    query = select(User).where(User.organization_id == current_user.organization_id)

    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if search:
        query = query.where(
            User.email.ilike(f"%{search}%") |
            User.first_name.ilike(f"%{search}%") |
            User.last_name.ilike(f"%{search}%")
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(User.last_name, User.first_name).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    users = result.scalars().all()

    return UserListResponse(items=users, total=total)


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user's profile."""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user's profile."""
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    await db.commit()
    await db.refresh(current_user)

    return current_user


@router.post("/me/change-password")
async def change_password(
    data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Change current user's password."""
    from api.routers.auth import verify_password

    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    current_user.password_hash = get_password_hash(data.new_password)
    await db.commit()

    return {"message": "Password changed successfully"}


@router.post("/me/device-token")
async def register_device_token(
    data: DeviceToken,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Register device token for push notifications."""
    current_user.device_token = data.device_token
    current_user.device_platform = data.device_platform
    await db.commit()

    return {"message": "Device token registered"}


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db)
):
    """Get user by ID. Requires Manager role."""
    result = await db.execute(
        select(User).where(
            and_(
                User.id == user_id,
                User.organization_id == current_user.organization_id
            )
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.put("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    data: UserRoleUpdate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Update user's role. Requires Admin role."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    result = await db.execute(
        select(User).where(
            and_(
                User.id == user_id,
                User.organization_id == current_user.organization_id
            )
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent demoting owners unless you're the owner
    if user.role == UserRole.OWNER and current_user.role != UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Cannot change owner's role")

    user.role = data.role
    await db.commit()
    await db.refresh(user)

    return user


@router.put("/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: uuid.UUID,
    data: UserStatusUpdate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Activate or deactivate a user. Requires Admin role."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own status")

    result = await db.execute(
        select(User).where(
            and_(
                User.id == user_id,
                User.organization_id == current_user.organization_id
            )
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = data.is_active
    await db.commit()
    await db.refresh(user)

    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Delete a user. Requires Admin role."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    result = await db.execute(
        select(User).where(
            and_(
                User.id == user_id,
                User.organization_id == current_user.organization_id
            )
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role == UserRole.OWNER:
        raise HTTPException(status_code=403, detail="Cannot delete organization owner")

    await db.delete(user)
    await db.commit()
