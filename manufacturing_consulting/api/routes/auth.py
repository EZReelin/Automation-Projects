"""
Authentication API routes.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from api.dependencies import DatabaseDep, CurrentUserDep
from services.auth_service import AuthService

router = APIRouter()


class LoginResponse(BaseModel):
    """Login response schema."""
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: dict


class RefreshRequest(BaseModel):
    """Token refresh request."""
    refresh_token: str


class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str
    first_name: str
    last_name: str


class ChangePasswordRequest(BaseModel):
    """Password change request."""
    current_password: str
    new_password: str


@router.post("/login", response_model=LoginResponse)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    db: DatabaseDep,
):
    """
    Authenticate user and get access token.
    
    - **username**: User email address
    - **password**: User password
    """
    auth_service = AuthService(db)
    
    result = await auth_service.authenticate(
        email=form_data.username,
        password=form_data.password,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return result


@router.post("/refresh", response_model=dict)
async def refresh_token(
    body: RefreshRequest,
    request: Request,
    db: DatabaseDep,
):
    """
    Refresh access token using refresh token.
    """
    auth_service = AuthService(db)
    
    result = await auth_service.refresh_tokens(
        refresh_token=body.refresh_token,
        ip_address=request.client.host if request.client else None,
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    
    return result


@router.post("/logout")
async def logout(
    current_user: CurrentUserDep,
    db: DatabaseDep,
    all_sessions: bool = False,
):
    """
    Logout current user.
    
    - **all_sessions**: If true, revoke all active sessions
    """
    auth_service = AuthService(db)
    
    await auth_service.logout(
        user_id=current_user["sub"],
        all_sessions=all_sessions,
    )
    
    return {"message": "Successfully logged out"}


@router.get("/me")
async def get_current_user(current_user: CurrentUserDep, db: DatabaseDep):
    """Get current user information."""
    return {
        "id": current_user["sub"],
        "email": current_user["email"],
        "tenant_id": current_user.get("tenant_id"),
        "role": current_user.get("role"),
        "system_role": current_user.get("system_role"),
    }


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: CurrentUserDep,
    db: DatabaseDep,
):
    """Change user password."""
    auth_service = AuthService(db)
    
    try:
        success = await auth_service.change_password(
            user_id=current_user["sub"],
            current_password=body.current_password,
            new_password=body.new_password,
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
        
        return {"message": "Password changed successfully"}
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
