"""
Database engine, session factory, and base model class.
All SQLAlchemy models import Base from here.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# SQLite engine – check_same_thread=False required for FastAPI async usage
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=settings.DEBUG,  # logs SQL statements in debug mode
)

# Every database session is created from this factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# All ORM models inherit from this base
Base = declarative_base()


def get_db():
    """
    FastAPI dependency that yields a database session.
    Guarantees the session is closed after each request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables() -> None:
    """Create all tables defined in ORM models (called on startup)."""
    # Import models here so SQLAlchemy registers them before create_all
    from app.models import user, project, meeting, requirement_candidate, requirement_similarity, follow_up_question, brd_document  # noqa: F401

    Base.metadata.create_all(bind=engine)
