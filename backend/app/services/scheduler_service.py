import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, BackgroundTasks
from app.core.database import get_db, SessionLocal
from app.core.logger import logger
from app.services.market_analyzer import MarketAnalyzer
from app.services.portfolio_service import portfolio_service
from app.core.config import settings
from app.services.crypto_service import crypto_service
from app.services.straddle_service import StraddleService, straddle_service
from app.services.notifications import notification_service
import asyncio
import pandas as pd
from app.services.telegram_service import TelegramService

#curd operations
from app.crud.curd_position import position_crud as curd_position

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
        self.is_running = False
        self.symbols = []

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

            # await self._analyze_market()
            # await self._update_portfolio()
            # await self._send_daily_summary()
            # await self._check_risk_limits()
        except Exception as e:
            logger.error(f"Error in hoverly schedule: {str(e)}")
            raise
        finally:
            # Release the processing lock
            SchedulerService._processing_locks[lock_key] = False

    async def _minute_schedule_start(self):
        """Execute minute-based schedule"""
        lock_key = "minute_schedule"

        # Skip if already processing
        if lock_key in SchedulerService._processing_locks and SchedulerService._processing_locks[lock_key]:
            logger.debug("Minute schedule already processing, skipping")
            return

        # Set processing lock
        SchedulerService._processing_locks[lock_key] = True

        try:
            #check if minute schedule is enabled
            if not self.minute_schedule_enabled:
                logger.debug("Minute schedule disabled, skipping")
                return

            from app.services.notifications import notification_service
            from app.services.telegram_service import TelegramService

            # Ensure notification service has current DB session
            if self.db and not notification_service.db:
                notification_service.set_db(self.db)

            # Get the telegram service singleton
            telegram_service = TelegramService.get_instance(db=self.db)

            # Don't try to initialize here - use the already initialized singleton
            # The telegram service should be initialized in main.py startup
            if not telegram_service._initialized:
                logger.debug("Telegram service not initialized, skipping telegram notifications in scheduler")
                # Continue without telegram notifications rather than trying to initialize

            straddle_service = StraddleService(self.db)
            #get in progress positions
            possions = await curd_position.get_in_progress_positions(self.db)
            for position in possions:
                await self.db.refresh(position)
                trading_status = await straddle_service.auto_buy_sell_straddle_inprogress(position.symbol)
                # Use the enhanced notification service for better formatting
                # await notification_service.send_straddle_status_notification(trading_status)


            return trading_status
        except Exception as e:
            logger.error(f"Error in minute schedule: {str(e)}")
            raise
        finally:
            # Release the processing lock
            SchedulerService._processing_locks[lock_key] = False

    async def _send_trading_status_to_telegram(self, trading_status):
        """Format and send trading status to Telegram"""
        try:
            if not trading_status:
                return

            symbol = trading_status.get('symbol', 'Unknown')
            status = trading_status.get('status', 'Unknown')

            # Skip sending certain statuses
            if status in ["SKIPPED", "DISABLED", "NO_POSITION"]:
                return

            # Format header message based on status
            if status == "MONITORING":
                header = f"🔍 *Monitoring {symbol}*"
            elif status == "PROFIT_TAKEN":
                header = f"💰 *Profit Taken for {symbol}*"
            elif status == "INITIATED":
                header = f"🚀 *New Straddle Started for {symbol}*"
            elif status == "RECREATED":
                header = f"🔄 *Straddle Recreated for {symbol}*"
            elif status == "ERROR":
                header = f"⚠️ *Error in Straddle for {symbol}*"
            else:
                header = f"📊 *Status Update for {symbol}*"

            # Get metrics
            metrics = trading_status.get('metrics', {})
            current_price = metrics.get('current_price', 0)
            profit_loss = metrics.get('profit_loss', 0)
            profit_loss_pct = metrics.get('profit_loss_percent', 0)

            # Format price with proper precision
            if current_price < 0.1:
                price_format = "${:.6f}"
            elif current_price < 1:
                price_format = "${:.5f}"
            elif current_price < 10:
                price_format = "${:.4f}"
            elif current_price < 1000:
                price_format = "${:.2f}"
            else:
                price_format = "${:,.2f}"

            # Format metrics message
            metrics_msg = (
                f"Current Price: {price_format.format(current_price)}\n"
                f"P/L: ${profit_loss:.2f} ({profit_loss_pct:.2f}%)"
            )

            # Add trend information if available
            if 'trend_direction' in metrics:
                trend_direction = metrics['trend_direction']
                trend_strength = metrics.get('trend_strength', 0)
                trend_emoji = "📈" if trend_direction == "up" else "📉"
                metrics_msg += f"\nTrend: {trend_emoji} {trend_direction.upper()} (Strength: {trend_strength})"

            # Add volatility if available
            if 'volatility' in metrics:
                volatility = metrics['volatility'] * 100  # Convert to percentage
                metrics_msg += f"\nVolatility: {volatility:.2f}%"

            # Add trade information if needed
            if status in ["INITIATED", "RECREATED"]:
                buy_trades = metrics.get('buy_trades', [])
                sell_trades = metrics.get('sell_trades', [])

                if buy_trades:
                    buy_price = buy_trades[0].get('entry_price', 0)
                    metrics_msg += f"\nBuy Entry: {price_format.format(buy_price)}"

                if sell_trades:
                    sell_price = sell_trades[0].get('entry_price', 0)
                    metrics_msg += f"\nSell Entry: {price_format.format(sell_price)}"

            # Add swap information if a swap was performed
            swap_info = ""
            swap_status = trading_status.get('swap_status', {})
            if swap_status.get('performed', False):
                from_coin = swap_status.get('from_coin', '')
                to_coin = swap_status.get('to_coin', '')
                amount = swap_status.get('amount', 0)
                price = swap_status.get('price', 0)

                swap_info = (
                    f"\n\n�� *Swap Performed*\n"
                    f"From: {from_coin}\n"
                    f"To: {to_coin}\n"
                    f"Amount: {amount:.4f}\n"
                    f"Price: {price_format.format(price)}"
                )

            # Add reason if available
            reason = trading_status.get('reason', '')
            reason_msg = f"\n\n_Reason: {reason}_" if reason else ""

            # Handle error messages
            error_msg = ""
            if status == "ERROR":
                error = trading_status.get('error', '')
                if error:
                    error_msg = f"\n\n❌ *Error*: {error}"

            # Combine all parts into final message
            message = f"{header}\n\n{metrics_msg}{swap_info}{reason_msg}{error_msg}"

            # Send message to Telegram
            await notification_service.send_message(message)

        except Exception as e:
            logger.error(f"Error sending trading status to Telegram: {str(e)}")
            # Don't re-raise to prevent disrupting the main process

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

            from app.services.notifications import notification_service
            # Ensure notification service has current DB session
            if self.db and not notification_service.db:
                notification_service.set_db(self.db)

            # Get the telegram service singleton
            telegram_service = TelegramService.get_instance(db=self.db)

            # Don't try to initialize here - use the already initialized singleton
            # The telegram service should be initialized in main.py startup
            if not telegram_service._initialized:
                logger.debug("Telegram service not initialized, skipping telegram notifications in auto trading")
                # Continue without telegram notifications rather than trying to initialize

            straddle_service = StraddleService(self.db)
            trading_status = await straddle_service.auto_buy_sell_straddle_inprogress('DOGE/USDT')

            # Use the enhanced notification method
            await notification_service.send_straddle_status_notification(trading_status)

            #second symbol
            trading_status = await straddle_service.auto_buy_sell_straddle_inprogress('TRUMP/USDT')
            # Use the enhanced notification method
            await notification_service.send_straddle_status_notification(trading_status)

            return trading_status
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

    async def start(self, symbols=None):
        """Start the scheduler with the given symbols"""
        if self.is_running:
            logger.info("Scheduler is already running")
            return

        if symbols:
            self.symbols = symbols
        elif not self.symbols:
            # Default to BTC if no symbols provided
            self.symbols = ["BTCUSDT"]

        logger.info(f"Starting portfolio summary scheduler for symbols: {self.symbols}")

        # Schedule portfolio summaries at different intervals
        self.scheduler.add_job(
            self.generate_portfolio_summary,
            IntervalTrigger(minutes=1),
            id="portfolio_summary_1min",
            replace_existing=True,
            args=[self.symbols[0]]  # Use the first symbol for summaries
        )

        # Add jobs for different lookback windows (just log different intervals, actual summary creation is the same)
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
            logger.info("Scheduler is not running")
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


# Create scheduler instance
scheduler_service = SchedulerService(None)  # Will be initialized with proper db session

# Function to start scheduler at application startup
async def start_scheduler_on_startup():
    # Get symbols from settings (if available)
    symbols = getattr(settings, "TRADING_SYMBOLS", ["BTCUSDT"])
    await scheduler_service.start(symbols)
