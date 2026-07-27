"""
User model – stores registered users and authentication data.
"""
from sqlalchemy import Boolean, Column, String, Text
from sqlalchemy.orm import relationship

from app.models.base_model import BaseModel


class User(BaseModel):
    """Represents an application user."""

    __tablename__ = "users"

    # ── Identity ──────────────────────────────────────────────────
    full_name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)

    # ── Authentication ────────────────────────────────────────────
    hashed_password = Column(String(255), nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    # ── Profile ───────────────────────────────────────────────────
    role = Column(String(50), default="user", nullable=False)  # user | admin
    bio = Column(Text, nullable=True)
    profile_picture = Column(String(500), nullable=True)

    # ── Relationships ─────────────────────────────────────────────
    # One user → many projects
    projects = relationship(
        "Project",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
