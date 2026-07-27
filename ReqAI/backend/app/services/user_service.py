"""
User service – all business logic for user operations.
Routers call this service; they never touch the DB directly.
"""
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.models.user import User
from app.schemas.user_schema import UserCreate, UserUpdate, UserPasswordUpdate, LoginRequest


class UserService:

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.query(User).filter(User.id == user_id, User.is_active == True).first()

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email.lower()).first()

    @staticmethod
    def get_by_username(db: Session, username: str) -> Optional[User]:
        return db.query(User).filter(User.username == username.lower()).first()

    # ── Registration ──────────────────────────────────────────────

    @staticmethod
    def register(db: Session, payload: UserCreate) -> User:
        """Create a new user account."""
        # Check uniqueness
        if UserService.get_by_email(db, payload.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )
        if UserService.get_by_username(db, payload.username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This username is already taken.",
            )

        user = User(
            full_name=payload.full_name,
            email=payload.email.lower(),
            username=payload.username.lower(),
            hashed_password=hash_password(payload.password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    # ── Authentication ────────────────────────────────────────────

    @staticmethod
    def authenticate(db: Session, payload: LoginRequest) -> dict:
        """Verify credentials and return JWT tokens."""
        identifier = payload.username_or_email.lower()

        # Accept login by email or username
        user = UserService.get_by_email(db, identifier) or UserService.get_by_username(db, identifier)

        if not user or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials.",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated.",
            )

        token_data = {"sub": str(user.id)}
        return {
            "access_token": create_access_token(token_data),
            "refresh_token": create_refresh_token(token_data),
            "token_type": "bearer",
            "user": user,
        }

    # ── Profile Update ────────────────────────────────────────────

    @staticmethod
    def update_profile(db: Session, user: User, payload: UserUpdate) -> User:
        """Update mutable profile fields."""
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def change_password(db: Session, user: User, payload: UserPasswordUpdate) -> User:
        """Verify current password then apply new hash."""
        if not verify_password(payload.current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect.",
            )
        user.hashed_password = hash_password(payload.new_password)
        db.commit()
        db.refresh(user)
        return user

    # ── Deactivation ──────────────────────────────────────────────

    @staticmethod
    def deactivate(db: Session, user: User) -> None:
        """Soft-delete: mark user as inactive instead of deleting."""
        user.is_active = False
        db.commit()
