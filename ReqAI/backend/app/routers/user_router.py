"""
User router – profile management, password change.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.schemas.common_schema import SuccessResponse
from app.schemas.user_schema import UserPasswordUpdate, UserResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/profile", response_model=UserResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return UserResponse.model_validate(current_user)


@router.put("/profile", response_model=UserResponse)
def update_profile(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update profile fields (full_name, bio, profile_picture)."""
    updated = UserService.update_profile(db, current_user, payload)
    return UserResponse.model_validate(updated)


@router.put("/password", response_model=SuccessResponse)
def change_password(
    payload: UserPasswordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change the authenticated user's password."""
    UserService.change_password(db, current_user, payload)
    return SuccessResponse(message="Password changed successfully.")


@router.delete("/account", response_model=SuccessResponse, status_code=status.HTTP_200_OK)
def deactivate_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete the authenticated user's account."""
    UserService.deactivate(db, current_user)
    return SuccessResponse(message="Account deactivated successfully.")
