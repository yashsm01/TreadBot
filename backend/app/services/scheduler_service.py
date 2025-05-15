import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from app.core.database import get_db
from app.core.logger import logger
from app.services.market_analyzer import MarketAnalyzer
from app.services.portfolio_service import portfolio_service
from app.core.config import settings
from app.services.crypto_service import crypto_service
from app.services.straddle_service import StraddleService
from app.services.notifications import notification_service
import asyncio
import pandas as pd

class StraddleMonitor:
    def __init__(self):
        self.monitoring_symbols: Dict[str, bool] = {}
        self.price_history: Dict[str, List[float]] = {}
        self.volume_history: Dict[str, List[float]] = {}
        self.history_size = 100  # Keep last 100 data points
        self.check_interval = 60  # Check every 60 seconds

    def add_symbol(self, symbol: str):
        """Add a symbol to monitor"""
        self.monitoring_symbols[symbol] = True
        self.price_history[symbol] = []
        self.volume_history[symbol] = []
        logger.info(f"Added {symbol} to straddle monitoring")

    def remove_symbol(self, symbol: str):
        """Remove a symbol from monitoring"""
        if symbol in self.monitoring_symbols:
            del self.monitoring_symbols[symbol]
            del self.price_history[symbol]
            del self.volume_history[symbol]
            logger.info(f"Removed {symbol} from straddle monitoring")

    def update_price_data(self, symbol: str, price: float, volume: float):
        """Update price and volume history for a symbol"""
        self.price_history[symbol].append(price)
        self.volume_history[symbol].append(volume)

        # Keep only last N data points
        if len(self.price_history[symbol]) > self.history_size:
            self.price_history[symbol] = self.price_history[symbol][-self.history_size:]
            self.volume_history[symbol] = self.volume_history[symbol][-self.history_size:]

class SchedulerService:
    # Add class variable for processing locks
    _processing_locks = {}

    def __init__(self, db: AsyncSession = Depends(get_db)):
        """Initialize the scheduler service"""
        self.db = db
        self.scheduler = AsyncIOScheduler()
        self.straddle_monitor = StraddleMonitor()

        # Schedule jobs
        self.minute_schedule_enabled = True
        self.hoverly_schedule_enabled = False
        self.daily_schedule_enabled = False
        self.minute_schedule_stop = self._minute_schedule_start
        self.hoverly_schedule_stop = self._hoverly_schedule_start

        # Control flags for scheduled jobs
        self.auto_trading_enabled = True
        self.market_analysis_enabled = False
        self.portfolio_update_enabled = False
        self.daily_summary_enabled = False
        self.risk_check_enabled = False
        self.monitoring_enabled = False

        self._setup_jobs()

    def _setup_jobs(self):
        """Setup scheduled jobs"""
        try:
            # Market analysis every hour
            self.scheduler.add_job(
                self._hoverly_schedule_start,
                CronTrigger(minute=0),  # Every hour at minute 0
                id='hoverly_schedule',
                replace_existing=True
            )

            # Portfolio update every 15 minutes
            self.scheduler.add_job(
                self._minute_schedule_start,
                IntervalTrigger(minutes=1),
                id='minute_schedule',
                replace_existing=True
            )

            # Daily summary at midnight
            self.scheduler.add_job(
                self._daily_schedule_start,
                CronTrigger(hour=0, minute=0),  # Every day at midnight
                id='daily_schedule',
                replace_existing=True
            )

            logger.info("Scheduled jobs setup completed")
        except Exception as e:
            logger.error(f"Error setting up scheduled jobs: {str(e)}")
            raise

    # Time based schedules start
    async def _daily_schedule_start(self):
        """Start the daily schedule"""
        # Check if this task is already running
        lock_key = "daily_schedule"
        if lock_key in SchedulerService._processing_locks and SchedulerService._processing_locks[lock_key]:
            logger.debug("Daily schedule already running, skipping")
            return

        try:
            # Set the processing lock
            SchedulerService._processing_locks[lock_key] = True

            #check if daily schedule is enabled
            if not self.daily_schedule_enabled:
                logger.debug("Daily schedule disabled, skipping")
                return

            result = await self._send_daily_summary()
            logger.info(f"Daily summary sent: {result}")
            SchedulerService._processing_locks[lock_key] = False
        except Exception as e:
            logger.error(f"Error in daily schedule: {str(e)}")
            raise
        finally:
            # Release the processing lock
            SchedulerService._processing_locks[lock_key] = False

    async def _hoverly_schedule_start(self):
        """Schedule the jobs"""
        # Check if this task is already running
        lock_key = "hoverly_schedule"
        if lock_key in SchedulerService._processing_locks and SchedulerService._processing_locks[lock_key]:
            logger.debug("Hourly schedule already running, skipping")
            return

        try:
            # Set the processing lock
            SchedulerService._processing_locks[lock_key] = True

            #check if hoverly schedule is enabled
            if not self.hoverly_schedule_enabled:
                logger.debug("Hoverly schedule disabled, skipping")
                return

            await self._analyze_market()
            await self._update_portfolio()
            await self._send_daily_summary()
            await self._check_risk_limits()
        except Exception as e:
            logger.error(f"Error in hoverly schedule: {str(e)}")
            raise
        finally:
            # Release the processing lock
            SchedulerService._processing_locks[lock_key] = False

    async def _minute_schedule_start(self):
        """Start the minute schedule"""
        # Check if this task is already running
        lock_key = "minute_schedule"
        if lock_key in SchedulerService._processing_locks and SchedulerService._processing_locks[lock_key]:
            logger.debug("Minute schedule already running, skipping")
            return

        try:
            # Set the processing lock
            SchedulerService._processing_locks[lock_key] = True

            #check if minute schedule is enabled
            if not self.minute_schedule_enabled:
                logger.debug("Minute schedule disabled, skipping")
                return

            straddle_service = StraddleService(self.db)
            await straddle_service.auto_buy_sell_straddle_inprogress('GUN/USDT')
        except Exception as e:
            logger.error(f"Error in minute schedule: {str(e)}")
            raise
        finally:
            # Release the processing lock
            SchedulerService._processing_locks[lock_key] = False

    # Time based schedules end
    async def _minute_schedule_stop(self):
        """Stop the minute schedule"""
        try:
            await self._stop_monitoring()
        except Exception as e:
            logger.error(f"Error in minute schedule stop: {str(e)}")
            raise
    async def _daily_schedule_stop(self):
        """Stop the daily schedule"""
        try:
            await self._stop_monitoring()
        except Exception as e:
            logger.error(f"Error in daily schedule stop: {str(e)}")
            raise
    async def _hoverly_schedule_stop(self):
        """Stop the hoverly schedule"""
        try:
            await self._stop_monitoring()
        except Exception as e:
            logger.error(f"Error in hoverly schedule stop: {str(e)}")
            raise

    #sub functions start

    #auto trading functions process
    async def auto_trading_process(self):
        """Perform auto trading process"""
        try:
            #check if auto trading is enabled
            if not self.auto_trading_enabled:
                logger.debug("Auto trading disabled, skipping")
                return

            await straddle_service.auto_buy_sell_straddle_inprogress('GUN/USDT')
        except Exception as e:
            logger.error(f"Error in auto trading process: {str(e)}")
            raise

    async def _analyze_market(self):
        """Perform market analysis and send notifications if needed"""
        if not self.market_analysis_enabled:
            logger.debug("Market analysis disabled, skipping")
            return

        try:
            # Create analyzer instance
            analyzer = MarketAnalyzer()

            # Get active trading pairs
            active_pairs = await analyzer.get_trading_pairs()

            for symbol in active_pairs:
                # Get market analysis
                analysis = await analyzer.get_market_analysis(symbol)

                # Check for significant market conditions
                if analysis.get('volatility', 0) > 0.02:  # 2% volatility threshold
                    await notification_service.send_message(
                        f"⚠️ High volatility detected for {symbol}: {analysis['volatility']*100:.2f}%"
                    )

            logger.info("Market analysis completed")
        except Exception as e:
            logger.error(f"Error in market analysis job: {str(e)}")

    async def _update_portfolio(self):
        """Update portfolio metrics"""
        if not self.portfolio_update_enabled:
            logger.debug("Portfolio update disabled, skipping")
            return

        try:
            # Get portfolio summary
            summary = await portfolio_service.get_portfolio_summary(self.db)

            # Check for significant changes
            if abs(summary.get('total_unrealized_pnl', 0)) > 1000:  # $1000 threshold
                await notification_service.send_message(
                    f"💰 Significant P/L change: ${summary['total_unrealized_pnl']:,.2f}"
                )

            logger.info("Portfolio update completed")
        except Exception as e:
            logger.error(f"Error in portfolio update job: {str(e)}")

    async def _send_daily_summary(self):
        """Send daily trading summary"""
        if not self.daily_summary_enabled:
            logger.debug("Daily summary disabled, skipping")
            return

        try:
            # Get performance metrics
            performance = await portfolio_service.get_trading_performance(self.db, days=1)

            summary = {
                "total_trades": performance['total_trades'],
                "winning_trades": performance['winning_trades'],
                "losing_trades": performance['losing_trades'],
                "net_profit": performance['total_profit'] - abs(performance['total_loss']),
                "win_rate": performance['win_rate']
            }

            # Send summary notification
            await notification_service.send_message(
                f"📊 Daily Trading Summary:\n"
                f"Total Trades: {summary['total_trades']}\n"
                f"Win Rate: {summary['win_rate']:.2f}%\n"
                f"Net P/L: ${summary['net_profit']:,.2f}"
            )

            logger.info("Daily summary sent")
        except Exception as e:
            logger.error(f"Error in daily summary job: {str(e)}")

    async def _check_risk_limits(self):
        """Check portfolio risk limits"""
        if not self.risk_check_enabled:
            logger.debug("Risk check disabled, skipping")
            return

        try:
            # Get active positions
            positions = await portfolio_service.get_position_metrics(self.db)

            for position in positions:
                # Check risk limits
                risk_check = await portfolio_service.check_risk_limits(
                    self.db,
                    position['symbol'],
                    position['total_quantity'],
                    position['average_entry']
                )

                if not risk_check['position_size_ok'] or not risk_check['volatility_ok']:
                    await notification_service.send_message(
                        f"⚠️ Risk limit exceeded for {position['symbol']}\n"
                        f"Position Size OK: {'✅' if risk_check['position_size_ok'] else '❌'}\n"
                        f"Volatility OK: {'✅' if risk_check['volatility_ok'] else '❌'}"
                    )

            logger.info("Risk check completed")
        except Exception as e:
            logger.error(f"Error in risk check job: {str(e)}")

    # Methods to control scheduled jobs
    def enable_market_analysis(self, enabled: bool = True):
        """Enable or disable market analysis job"""
        self.market_analysis_enabled = enabled
        logger.info(f"Market analysis {'enabled' if enabled else 'disabled'}")

    def enable_portfolio_update(self, enabled: bool = True):
        """Enable or disable portfolio update job"""
        self.portfolio_update_enabled = enabled
        logger.info(f"Portfolio update {'enabled' if enabled else 'disabled'}")

    def enable_daily_summary(self, enabled: bool = True):
        """Enable or disable daily summary job"""
        self.daily_summary_enabled = enabled
        logger.info(f"Daily summary {'enabled' if enabled else 'disabled'}")

    def enable_risk_check(self, enabled: bool = True):
        """Enable or disable risk check job"""
        self.risk_check_enabled = enabled
        logger.info(f"Risk check {'enabled' if enabled else 'disabled'}")

    async def start(self):
        """Start the scheduler"""
        try:
            if not self.scheduler.running:
                self.scheduler.start()
                logger.info("Scheduler started successfully")
        except Exception as e:
            logger.error(f"Error starting scheduler: {str(e)}")
            raise

    async def stop(self):
        """Stop the scheduler"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown()
                logger.info("Scheduler stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {str(e)}")
            raise

    async def start_monitoring(self):
        """Start the monitoring service"""
        self.monitoring_enabled = True
        self.running = True
        logger.info("Starting straddle monitoring service")

        while self.running and self.monitoring_enabled:
            try:
                await asyncio.sleep(self.straddle_monitor.check_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                await asyncio.sleep(5)  # Short delay before retry

    async def stop_monitoring(self):
        """Stop the monitoring service"""
        self.monitoring_enabled = False
        self.running = False
        logger.info("Stopping straddle monitoring service")



scheduler_service = SchedulerService(None)  # Will be initialized with proper db session
