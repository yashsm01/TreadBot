from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from .core.database import SessionLocal, engine, Base, get_db
from .core.config import settings
from .api.v1.api import api_router
from .services.telegram_service import create_telegram_service, telegram_service
from .services.crypto_service import crypto_service
from .services.scheduler_service import scheduler_service
from .services.portfolio_service import portfolio_service
from .core.exchange.exchange_manager import exchange_manager

# Import all models to ensure they are registered with Base
from .models.portfolio import Portfolio
from .models.trade import Trade
from .models.crypto import Cryptocurrency, CryptoPair
from .models.telegram import TelegramUser, TelegramNotification

telegram_srv = True
scheduler_srv = True

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

# Initialize services with DB session
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        logger.info("Starting application initialization...")

        # Initialize database session
        async with SessionLocal() as db:
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
                # Access and initialize the telegram service singleton
                logger.info("Initializing Telegram service...")
                from app.services.telegram_service import TelegramService
                global telegram_service
                # Get the singleton instance and update its DB session
                telegram_service = TelegramService.get_instance(db=db)

                # Initialize Telegram bot
                logger.info("Initializing Telegram bot...")
                await telegram_service.initialize()

                # Initialize notification service AFTER telegram service is initialized
                from app.services.notifications import notification_service
                notification_service.set_db(db)
                # Force initialization of the telegram service in notification service
                await notification_service._get_telegram_service()
                logger.info("Notification service initialized with database session and Telegram service")
            else:
                # Initialize notification service without Telegram
                from app.services.notifications import notification_service
                notification_service.set_db(db)
                logger.info("Notification service initialized with database session (Telegram disabled)")

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
