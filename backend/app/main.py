from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .routes.v1 import trade_routes, analysis_routes
from .services.telegram_service import telegram_service
from .services.crypto_service import crypto_service
from .services.scheduler_service import scheduler_service
from .core.database import SessionLocal
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description=settings.PROJECT_DESCRIPTION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(
    trade_routes.router,
    prefix=f"{settings.API_V1_STR}/trades",
    tags=["trades"]
)

app.include_router(
    analysis_routes.router,
    prefix=f"{settings.API_V1_STR}/analysis",
    tags=["analysis"]
)

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        # Initialize database session
        db = SessionLocal()

        # Initialize services with database session
        crypto_service.db = db
        scheduler_service.db = db

        # Initialize Telegram bot
        await telegram_service.initialize(db)

        # Start scheduler
        await scheduler_service.start()

        logger.info("Application startup completed successfully")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    try:
        # Stop scheduler
        await scheduler_service.stop()

        # Stop Telegram bot
        await telegram_service.stop()

        logger.info("Application shutdown completed successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "environment": "paper" if settings.PAPER_TRADING else "live",
        "version": settings.PROJECT_VERSION,
        "telegram_bot": telegram_service._initialized,
        "scheduler": scheduler_service.scheduler.running
    }
