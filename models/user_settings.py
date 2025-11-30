from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserProfileUpdate(BaseModel):
    """Update user profile information"""
    display_name: Optional[str] = None
    bio: Optional[str] = None
    profile_picture_url: Optional[str] = None
    username: Optional[str] = None
    email: Optional[EmailStr] = None


class UserProfileResponse(BaseModel):
    """User profile information"""
    id: int
    username: str
    email: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    profile_picture_url: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class DeleteAccountRequest(BaseModel):
    """Request to delete account"""
    password: str  # Require password confirmation for security


class DeleteAccountResponse(BaseModel):
    """Response after account deletion"""
    success: bool
    message: str


class LogoutResponse(BaseModel):
    """Response after logout"""
    success: bool
    message: str

