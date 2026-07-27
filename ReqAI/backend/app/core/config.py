"""
Application configuration.
All settings are loaded from environment variables with safe defaults.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the backend root
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class Settings:
    # ── Application ──────────────────────────────────────────────
    APP_NAME: str = os.getenv("APP_NAME", "ReqAI")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    APP_DESCRIPTION: str = os.getenv(
        "APP_DESCRIPTION",
        "AI Powered Business Requirement Document Generator",
    )
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    API_V1_PREFIX: str = "/api/v1"

    # ── Security ─────────────────────────────────────────────────
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", "change-this-secret-key-in-production-please"
    )
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(
        os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")
    )

    # ── Database ──────────────────────────────────────────────────
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite:///./reqai.db"
    )

    # ── CORS ─────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:5500,http://127.0.0.1:5500",
    ).split(",")

    # ── File Storage ─────────────────────────────────────────────
    BASE_DIR: Path = Path(__file__).resolve().parents[2]
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    GENERATED_DIR: Path = BASE_DIR / "generated"
    LOGS_DIR: Path = BASE_DIR / "logs"

    # Max audio upload size: 100 MB
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100"))

    # ── Logging ───────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = str(LOGS_DIR / "reqai.log")


# Singleton instance used across the application
settings = Settings()
