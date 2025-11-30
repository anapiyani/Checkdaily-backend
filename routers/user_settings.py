from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from models.user_settings import (
    UserProfileUpdate,
    UserProfileResponse,
    DeleteAccountRequest,
    DeleteAccountResponse,
    LogoutResponse
)
from models.db_user import DBUser
from database import get_db
from routers.auth import get_current_user, verify_password

router = APIRouter(prefix="/api/v1/user", tags=["user"])

security = HTTPBearer()


def get_user_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> DBUser:
    """Get current user from JWT token"""
    token = credentials.credentials
    user = get_current_user(token, db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    return user


@router.get("/settings", response_model=UserProfileResponse)
async def get_user_settings(
    user: DBUser = Depends(get_user_from_token)
):
    """
    Get current user's profile/settings
    
    Returns all user profile information
    """
    return UserProfileResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        bio=user.bio,
        profile_picture_url=user.profile_picture_url,
        created_at=user.created_at
    )


@router.put("/settings", response_model=UserProfileResponse)
async def update_user_settings(
    profile_data: UserProfileUpdate,
    user: DBUser = Depends(get_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Update user profile/settings
    
    Can update:
    - display_name
    - bio
    - profile_picture_url
    - username (must be unique)
    - email (must be unique)
    """

    if profile_data.username is not None and profile_data.username != user.username:
        existing_user = db.query(DBUser).filter(
            DBUser.username == profile_data.username,
            DBUser.id != user.id
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        user.username = profile_data.username
    
    if profile_data.email is not None and profile_data.email != user.email:
        existing_user = db.query(DBUser).filter(
            DBUser.email == profile_data.email,
            DBUser.id != user.id
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        user.email = profile_data.email
    
    if profile_data.display_name is not None:
        user.display_name = profile_data.display_name
    if profile_data.bio is not None:
        user.bio = profile_data.bio
    if profile_data.profile_picture_url is not None:
        user.profile_picture_url = profile_data.profile_picture_url
    
    db.commit()
    db.refresh(user)
    
    return UserProfileResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        bio=user.bio,
        profile_picture_url=user.profile_picture_url,
        created_at=user.created_at
    )


@router.delete("/account", response_model=DeleteAccountResponse)
async def delete_account(
    request: DeleteAccountRequest,
    user: DBUser = Depends(get_user_from_token),
    db: Session = Depends(get_db)
):
    """
    Delete user account
    
    Requires password confirmation for security.
    This will permanently delete:
    - User account
    - All associated checks
    - All day statuses
    
    This action cannot be undone.
    """
    # Verify password before deletion
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password"
        )
    
    # Delete user (cascade will delete all checks and day statuses)
    db.delete(user)
    db.commit()
    
    return DeleteAccountResponse(
        success=True,
        message="Account deleted successfully"
    )

