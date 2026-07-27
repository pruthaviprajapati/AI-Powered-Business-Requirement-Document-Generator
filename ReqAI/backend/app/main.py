"""
ReqAI – FastAPI application entry point.
All routers, middleware, and startup logic are wired here.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging_config import setup_logging, get_logger
from app.database.db import create_all_tables
from app.middleware.request_logger import RequestLoggerMiddleware
from app.routers import auth_router, user_router, project_router, meeting_router
from app.utils.file_utils import ensure_directories_exist

# ── Logging ───────────────────────────────────────────────────────────────────
setup_logging()
logger = get_logger(__name__)

# ── Application factory ───────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Custom middleware ─────────────────────────────────────────────────────────
app.add_middleware(RequestLoggerMiddleware)

# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url.path, str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "An internal server error occurred."},
    )

# ── Startup / shutdown ────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    logger.info("Starting %s v%s ...", settings.APP_NAME, settings.APP_VERSION)
    ensure_directories_exist()
    create_all_tables()
    logger.info("Database tables verified.")
    logger.info("Application ready.")


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("%s shutting down.", settings.APP_NAME)

# ── API routers (versioned under /api/v1) ─────────────────────────────────────
PREFIX = settings.API_V1_PREFIX

app.include_router(auth_router.router, prefix=PREFIX)
app.include_router(user_router.router, prefix=PREFIX)
app.include_router(project_router.router, prefix=PREFIX)
app.include_router(meeting_router.router, prefix=PREFIX)

# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}

# ── Root ──────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Root"])
def root():
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "docs": "/api/docs",
        "version": settings.APP_VERSION,
    }
