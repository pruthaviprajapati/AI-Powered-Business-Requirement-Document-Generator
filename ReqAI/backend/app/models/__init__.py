# models package – import all models so SQLAlchemy registers them
from app.models.user import User
from app.models.project import Project
from app.models.meeting import Meeting
from app.models.requirement_candidate import RequirementCandidate

__all__ = ["User", "Project", "Meeting", "RequirementCandidate"]
