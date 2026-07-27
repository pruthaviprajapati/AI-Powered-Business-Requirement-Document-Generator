"""
Authentication router – register, login, logout, token refresh.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.security import create_access_token, decode_token
from app.database.db import get_db
from app.models.user import User
from app.schemas.common_schema import SuccessResponse
from app.schemas.user_schema import (
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.services.user_service import UserService
from fastapi import HTTPException, status as http_status

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=SuccessResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Register a new user account."""
    user = UserService.register(db, payload)
    return SuccessResponse(
        message="Account created successfully.",
        data=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user and return JWT tokens."""
    result = UserService.authenticate(db, payload)
    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        token_type=result["token_type"],
        user=UserResponse.model_validate(result["user"]),
    )


@router.post("/refresh", response_model=dict)
def refresh_token(payload: RefreshTokenRequest):
    """Exchange a valid refresh token for a new access token."""
    token_data = decode_token(payload.refresh_token)

    if token_data is None or token_data.get("type") != "refresh":
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    new_access_token = create_access_token({"sub": token_data["sub"]})
    return {"access_token": new_access_token, "token_type": "bearer"}


@router.post("/logout", response_model=SuccessResponse)
def logout(current_user: User = Depends(get_current_user)):
    """
    Logout endpoint. JWT is stateless so logout is handled client-side
    by discarding the token. This endpoint acknowledges the action.
    """
    return SuccessResponse(message="Logged out successfully.")


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)
