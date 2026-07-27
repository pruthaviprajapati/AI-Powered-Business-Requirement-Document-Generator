"""
Project model – a container that groups related meetings.
"""
from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base_model import BaseModel


class Project(BaseModel):
    """Represents a software project that has requirement meetings."""

    __tablename__ = "projects"

    # ── Basic Information ─────────────────────────────────────────
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    client_name = Column(String(200), nullable=True)
    client_email = Column(String(255), nullable=True)
    status = Column(
        String(50), default="active", nullable=False
    )  # active | archived | completed

    # ── Ownership ─────────────────────────────────────────────────
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # ── Relationships ─────────────────────────────────────────────
    owner = relationship("User", back_populates="projects")

    # One project → many meetings
    meetings = relationship(
        "Meeting",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<Project id={self.id} name={self.name!r}>"
