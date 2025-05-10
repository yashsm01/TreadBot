from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import logging

from .database import SessionLocal, engine, Base
from .core.config import settings
from .api.v1.api import api_router
from .services.telegram_service import create_telegram_service, telegram_service
from .services.crypto_service import crypto_service
from .services.scheduler_service import scheduler_service
from .services.portfolio_service import portfolio_service
from .core.exchange.exchange_manager import exchange_manager

# Import all models to ensure they are registered with Base
from .models.portfolio import Portfolio, Transaction
from .models.trade import Trade
from .models.position import Position
from .models.crypto import Cryptocurrency, CryptoPair
from .models.telegram import TelegramUser, TelegramNotification

telegram_srv = True
scheduler_srv = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
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

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize services with DB session
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        logger.info("Starting application initialization...")

        # Force drop all tables and recreate them
        # logger.info("Dropping all tables...")
        # Base.metadata.drop_all(bind=engine)

        # Create database tables
        # logger.info("Creating database tables...")
        # Base.metadata.create_all(bind=engine)

        # Initialize database session
        db = SessionLocal()
        logger.info("Database session initialized")

        # Initialize exchange manager first
        logger.info("Initializing exchange manager...")
        exchange_manager.db = db
        await exchange_manager.initialize()
        logger.info("Exchange manager initialized successfully")

        # Initialize other services with database session
        logger.info("Initializing services...")
        crypto_service.db = db
        scheduler_service.db = db
        portfolio_service.db = db

        if(telegram_srv):
            # Create and initialize telegram service
            logger.info("Creating telegram service...")
            global telegram_service
            telegram_service = create_telegram_service(db)

            # Initialize Telegram bot
            logger.info("Initializing Telegram bot...")
            await telegram_service.initialize()

        if(scheduler_srv):
            # Start scheduler
            logger.info("Starting scheduler...")
            await scheduler_service.start()

        logger.info("Application startup completed successfully")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    try:
        logger.info("Starting application shutdown...")

        # Stop scheduler
        logger.info("Stopping scheduler...")
        await scheduler_service.stop()
        logger.info("Scheduler stopped successfully")

        # Stop Telegram bot
        logger.info("Stopping Telegram bot...")
        await telegram_service.stop()
        logger.info("Telegram bot stopped")

        # Close exchange connection
        logger.info("Closing exchange connection...")
        await exchange_manager.close()
        logger.info("Exchange connection closed")

        logger.info("Application shutdown completed successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
        raise

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "environment": "paper" if settings.PAPER_TRADING else "live",
        "version": settings.PROJECT_VERSION,
        "telegram_bot": telegram_service._initialized,
        "scheduler": scheduler_service.scheduler.running,
        "exchange": exchange_manager._initialized
    }

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)
