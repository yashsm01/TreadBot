from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import asyncio

from app.core.logger import logger
from app.core.database import SessionLocal
from app.services.straddle_service import straddle_service
from app.core.config import settings

class PortfolioSchedulerService:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self.symbols = []

    async def start(self, symbols=None):
        """Start the scheduler with the given symbols"""
        if self.is_running:
            logger.info("Portfolio scheduler is already running")
            return

        if symbols:
            self.symbols = symbols
        elif not self.symbols:
            # Default to BTC if no symbols provided
            self.symbols = ["BTCUSDT"]

        logger.info(f"Starting portfolio summary scheduler for symbols: {self.symbols}")


        # Add additional logging for other intervals
        self.scheduler.add_job(
            self.log_summary_interval,
            IntervalTrigger(minutes=5),
            id="portfolio_summary_5min",
            replace_existing=True,
            args=["5-minute"]
        )

        self.scheduler.add_job(
            self.log_summary_interval,
            IntervalTrigger(minutes=15),
            id="portfolio_summary_15min",
            replace_existing=True,
            args=["15-minute"]
        )

        self.scheduler.add_job(
            self.log_summary_interval,
            IntervalTrigger(minutes=60),
            id="portfolio_summary_60min",
            replace_existing=True,
            args=["1-hour"]
        )

        # Start the scheduler
        self.scheduler.start()
        self.is_running = True
        logger.info("Portfolio summary scheduler started successfully")

    async def stop(self):
        """Stop the scheduler"""
        if not self.is_running:
            logger.info("Portfolio scheduler is not running")
            return

        self.scheduler.shutdown()
        self.is_running = False
        logger.info("Portfolio summary scheduler stopped")

    async def generate_portfolio_summary(self, symbol):
        """Generate a portfolio summary snapshot"""
        try:
            # Create a new db session for this task
            async with SessionLocal() as db:
                # Initialize straddle service with the session
                straddle_svc = straddle_service
                straddle_svc.db = db

                # Update portfolio summary
                logger.info(f"Generating portfolio summary for {symbol}")
                summary = await straddle_svc.update_portfolio_summary(symbol)

                # Log success
                logger.info(f"Successfully created portfolio summary. Total value: ${summary.get('total_value', 0):.2f}")

        except Exception as e:
            logger.error(f"Error generating portfolio summary: {str(e)}")

    async def log_summary_interval(self, interval):
        """Just log that this interval has been triggered"""
        logger.info(f"Portfolio summary {interval} interval triggered")


# Create scheduler instance
portfolio_scheduler = PortfolioSchedulerService()

# Function to start scheduler at application startup
async def start_portfolio_scheduler():
    # Get symbols from settings (if available)
    symbols = getattr(settings, "TRADING_SYMBOLS", ["BTCUSDT"])
    await portfolio_scheduler.start(symbols)
