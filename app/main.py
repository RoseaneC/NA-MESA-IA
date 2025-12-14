from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .core.logging import logger
from .core.responses import UTF8JSONResponse
from .db.base import Base
from .db.session import engine
from .api import webhook, admin

# Optional fallback for local dev only
if settings.auto_create_db:
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("AUTO_CREATE_DB enabled: tables created via metadata.")
    except Exception as e:
        logger.error(f"Error creating database tables with AUTO_CREATE_DB: {e}")
        raise

# Create FastAPI app
app = FastAPI(
    title="VEXIA - WhatsApp Real",
    description="Sistema de combate à fome via WhatsApp",
    version="1.0.0",
    default_response_class=UTF8JSONResponse,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info("Starting VEXIA application...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Database: {settings.database_url}")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("Shutting down VEXIA application...")
