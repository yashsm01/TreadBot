import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from typing import Dict, List
from ..trader.strategy import StraddleStrategy
from ..trader.ccxt_utils import ExchangeManager
from ..services.telegram import TelegramService

logger = logging.getLogger(__name__)

class TradingScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.exchange_manager = ExchangeManager()
        self.telegram_service = TelegramService()
        self.active_strategies: Dict[str, StraddleStrategy] = {}
        self.job_ids: List[str] = []

    def start(self):
        try:
            self.scheduler.start()
            logger.info("Trading scheduler started successfully")
        except Exception as e:
            logger.error(f"Error starting scheduler: {str(e)}")
            raise

    def stop(self):
        try:
            self.scheduler.shutdown()
            logger.info("Trading scheduler stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {str(e)}")
            raise

    def add_trading_job(self, symbol: str, interval: str, config: Dict):
        try:
            # Create strategy instance
            strategy = StraddleStrategy(
                self.exchange_manager.get_exchange(),
                config
            )
            self.active_strategies[symbol] = strategy

            # Schedule the job
            job_id = f"{symbol}_{interval}"
            self.scheduler.add_job(
                self._execute_strategy,
                IntervalTrigger(minutes=self._parse_interval(interval)),
                id=job_id,
                args=[symbol],
                replace_existing=True
            )
            self.job_ids.append(job_id)

            logger.info(f"Added trading job for {symbol} with interval {interval}")
        except Exception as e:
            logger.error(f"Error adding trading job for {symbol}: {str(e)}")
            raise

    def remove_trading_job(self, symbol: str):
        try:
            job_id = f"{symbol}_*"
            self.scheduler.remove_job(job_id)
            if symbol in self.active_strategies:
                del self.active_strategies[symbol]
            logger.info(f"Removed trading job for {symbol}")
        except Exception as e:
            logger.error(f"Error removing trading job for {symbol}: {str(e)}")
            raise

    async def _execute_strategy(self, symbol: str):
        try:
            strategy = self.active_strategies.get(symbol)
            if not strategy:
                logger.warning(f"No strategy found for {symbol}")
                return

            # Execute the strategy
            trade = await strategy.execute_strategy(symbol)

            # Send notification
            await self.telegram_service.send_trade_notification(
                "STRADDLE",
                symbol,
                trade.entry_price,
                trade.quantity
            )

        except Exception as e:
            error_message = f"Error executing strategy for {symbol}: {str(e)}"
            logger.error(error_message)
            await self.telegram_service.send_error_notification(error_message)

    def _parse_interval(self, interval: str) -> int:
        """Convert interval string (e.g., '5m', '1h') to minutes"""
        try:
            if interval.endswith('m'):
                return int(interval[:-1])
            elif interval.endswith('h'):
                return int(interval[:-1]) * 60
            else:
                raise ValueError(f"Invalid interval format: {interval}")
        except Exception as e:
            logger.error(f"Error parsing interval {interval}: {str(e)}")
            raise
