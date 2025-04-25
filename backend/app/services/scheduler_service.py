import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from ..core.logger import logger
from ..services.telegram_service import telegram_service
from ..services.market_analyzer import market_analyzer
from ..services.portfolio_service import portfolio_service

class SchedulerService:
    def __init__(self, db: Session):
        """Initialize the scheduler service"""
        self.db = db
        self.scheduler = AsyncIOScheduler()
        self._setup_jobs()

    def _setup_jobs(self):
        """Setup scheduled jobs"""
        try:
            # Market analysis every hour
            self.scheduler.add_job(
                self._analyze_market,
                CronTrigger(minute=0),  # Every hour at minute 0
                id='market_analysis',
                replace_existing=True
            )

            # Portfolio update every 15 minutes
            self.scheduler.add_job(
                self._update_portfolio,
                IntervalTrigger(minutes=15),
                id='portfolio_update',
                replace_existing=True
            )

            # Daily summary at midnight
            self.scheduler.add_job(
                self._send_daily_summary,
                CronTrigger(hour=0, minute=0),  # Every day at midnight
                id='daily_summary',
                replace_existing=True
            )

            # Risk check every 5 minutes
            self.scheduler.add_job(
                self._check_risk_limits,
                IntervalTrigger(minutes=5),
                id='risk_check',
                replace_existing=True
            )

            logger.info("Scheduled jobs setup completed")
        except Exception as e:
            logger.error(f"Error setting up scheduled jobs: {str(e)}")
            raise

    async def _analyze_market(self):
        """Perform market analysis and send notifications if needed"""
        try:
            # Get active trading pairs
            active_pairs = await market_analyzer.get_active_pairs()

            for symbol in active_pairs:
                # Get market analysis
                analysis = await market_analyzer.get_market_analysis(symbol)

                # Check for significant market conditions
                if analysis.get('volatility', 0) > 0.02:  # 2% volatility threshold
                    await telegram_service.send_notification(
                        self.db,
                        user_id=1,  # TODO: Get from settings
                        message_type="MARKET_ALERT",
                        content=f"High volatility detected for {symbol}: {analysis['volatility']*100:.2f}%",
                        symbol=symbol
                    )

            logger.info("Market analysis completed")
        except Exception as e:
            logger.error(f"Error in market analysis job: {str(e)}")

    async def _update_portfolio(self):
        """Update portfolio metrics"""
        try:
            # Get portfolio summary
            summary = await portfolio_service.get_portfolio_summary(self.db)

            # Check for significant changes
            if abs(summary.get('total_unrealized_pnl', 0)) > 1000:  # $1000 threshold
                await telegram_service.send_notification(
                    self.db,
                    user_id=1,  # TODO: Get from settings
                    message_type="PORTFOLIO_ALERT",
                    content=f"Significant P/L change: ${summary['total_unrealized_pnl']:,.2f}",
                    symbol=None
                )

            logger.info("Portfolio update completed")
        except Exception as e:
            logger.error(f"Error in portfolio update job: {str(e)}")

    async def _send_daily_summary(self):
        """Send daily trading summary"""
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
            await telegram_service.send_notification(
                self.db,
                user_id=1,  # TODO: Get from settings
                message_type="DAILY_SUMMARY",
                content=f"Daily Trading Summary:\n" +
                       f"Total Trades: {summary['total_trades']}\n" +
                       f"Win Rate: {summary['win_rate']:.2f}%\n" +
                       f"Net P/L: ${summary['net_profit']:,.2f}",
                symbol=None
            )

            logger.info("Daily summary sent")
        except Exception as e:
            logger.error(f"Error in daily summary job: {str(e)}")

    async def _check_risk_limits(self):
        """Check portfolio risk limits"""
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
                    await telegram_service.send_notification(
                        self.db,
                        user_id=1,  # TODO: Get from settings
                        message_type="RISK_ALERT",
                        content=f"Risk limit exceeded for {position['symbol']}\n" +
                               f"Position Size OK: {risk_check['position_size_ok']}\n" +
                               f"Volatility OK: {risk_check['volatility_ok']}",
                        symbol=position['symbol']
                    )

            logger.info("Risk check completed")
        except Exception as e:
            logger.error(f"Error in risk check job: {str(e)}")

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

scheduler_service = SchedulerService(None)  # Will be initialized with proper db session
