import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from ..core.logger import logger
from ..services.market_analyzer import MarketAnalyzer
from ..services.portfolio_service import portfolio_service
from ..core.config import settings
from ..services.crypto_service import crypto_service
from ..services.straddle_service import straddle_service
from ..services.notifications import notification_service
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
    def __init__(self, db: Session):
        """Initialize the scheduler service"""
        self.db = db
        self.scheduler = AsyncIOScheduler()
        self.straddle_monitor = StraddleMonitor()
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
        self.running = True
        logger.info("Starting straddle monitoring service")

        while self.running:
            try:
                await self.check_opportunities()
                await asyncio.sleep(self.straddle_monitor.check_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                await asyncio.sleep(5)  # Short delay before retry

    async def stop_monitoring(self):
        """Stop the monitoring service"""
        self.running = False
        logger.info("Stopping straddle monitoring service")

    async def check_opportunities(self):
        """Check for straddle opportunities across monitored symbols"""
        for symbol in list(self.straddle_monitor.monitoring_symbols.keys()):
            try:
                # Get latest market data
                market_data = await crypto_service.get_market_data(symbol)
                if not market_data:
                    continue

                current_price = market_data["price"]
                current_volume = market_data["volume"]

                # Update historical data
                self.straddle_monitor.update_price_data(
                    symbol, current_price, current_volume
                )

                # Check if we have enough historical data
                if len(self.straddle_monitor.price_history[symbol]) < 20:  # Need minimum data for indicators
                    continue

                # Convert to pandas series for analysis
                prices = pd.Series(self.straddle_monitor.price_history[symbol])
                volumes = pd.Series(self.straddle_monitor.volume_history[symbol])

                # Analyze market conditions
                breakout_signal = await straddle_service.analyze_market_conditions(
                    symbol, prices, volumes
                )

                if breakout_signal:
                    # Check if signal confidence meets minimum threshold
                    if breakout_signal.confidence >= straddle_service.strategy.min_confidence:
                        # Handle breakout
                        activated_trade = await straddle_service.handle_breakout(
                            symbol, breakout_signal
                        )

                        if activated_trade:
                            logger.info(
                                f"Activated {activated_trade.side} trade for {symbol} "
                                f"at {activated_trade.entry_price}"
                            )

                # Check for potential new straddle setups
                if self._should_create_new_straddle(symbol, prices, volumes):
                    position_size = straddle_service.strategy.position_size
                    await straddle_service.create_straddle_trades(
                        symbol, current_price, position_size
                    )

            except Exception as e:
                logger.error(f"Error processing {symbol}: {str(e)}")

    def _should_create_new_straddle(self,
                                   symbol: str,
                                   prices: pd.Series,
                                   volumes: pd.Series) -> bool:
        """
        Determine if we should create a new straddle setup based on market conditions
        """
        try:
            # Check if we already have pending trades
            pending_trades = trade_crud.get_multi_by_symbol_and_status(
                None, symbol=symbol, status="PENDING"
            )
            if pending_trades:
                return False

            # Calculate volatility (using standard deviation)
            volatility = prices.pct_change().std()
            avg_volatility = prices.pct_change().rolling(window=20).std().mean()

            # Check for low volatility condition (squeeze)
            is_low_volatility = volatility < avg_volatility * 0.7

            # Check for sideways price action
            price_range = (prices.max() - prices.min()) / prices.mean()
            is_sideways = price_range < 0.02  # 2% range

            # Check for decreasing volume
            volume_trend = volumes.pct_change().mean()
            is_volume_decreasing = volume_trend < 0

            return is_low_volatility and is_sideways and is_volume_decreasing

        except Exception as e:
            logger.error(f"Error in should_create_new_straddle: {str(e)}")
            return False

scheduler_service = SchedulerService(None)  # Will be initialized with proper db session
