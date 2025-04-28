import ccxt.async_support as ccxt
import logging
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from ...services.crypto_service import crypto_service

logger = logging.getLogger(__name__)

class ExchangeManager:
    def __init__(self, db: Session = None, exchange_id: str = "binance"):
        """
        Initialize the exchange manager.

        Args:
            db: SQLAlchemy database session
            exchange_id: Exchange identifier (default: "binance")
        """
        self.exchange_id = exchange_id
        self.db = db
        self.exchange = None
        self._initialized = False

    async def initialize(self):
        """Initialize the exchange connection"""
        if self._initialized:
            return

        try:
            exchange_class = getattr(ccxt, self.exchange_id)
            self.exchange = exchange_class({
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot'
                }
            })
            self._initialized = True
            logger.info(f"Exchange {self.exchange_id} initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize exchange: {str(e)}")
            raise

    def get_all_active_pairs(self) -> List[str]:
        """Get all active trading pairs from the database"""
        try:
            return crypto_service.get_all_active_pairs()
        except Exception as e:
            logger.error(f"Error getting active pairs: {str(e)}")
            return []

    async def validate_trading_pair(self, symbol: str) -> bool:
        """
        Validate if a trading pair is supported by checking if we can fetch its ticker.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')

        Returns:
            bool: True if the trading pair is valid and supported, False otherwise
        """
        if not self._initialized:
            await self.initialize()

        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return ticker is not None
        except Exception as e:
            logger.error(f"Error validating trading pair {symbol}: {str(e)}")
            return False

    async def get_ticker(self, symbol: str) -> Optional[Dict]:
        """
        Get current ticker information for a symbol.

        Args:
            symbol: Trading pair symbol

        Returns:
            Optional[Dict]: Ticker information or None if error occurs
        """
        if not self._initialized:
            await self.initialize()

        try:
            if not await self.validate_trading_pair(symbol):
                logger.warning(f"Invalid or inactive trading pair: {symbol}")
                return None

            ticker = await self.exchange.fetch_ticker(symbol)
            return {
                'symbol': symbol,
                'last': ticker['last'],
                'bid': ticker['bid'],
                'ask': ticker['ask'],
                'volume': ticker['baseVolume'],
                'timestamp': ticker['timestamp']
            }
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {str(e)}")
            return None

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = '1m',
        limit: int = 100
    ) -> Optional[List]:
        """
        Get OHLCV data for a symbol.

        Args:
            symbol: Trading pair symbol
            timeframe: Time interval (default: '1m')
            limit: Number of candles to fetch (default: 100)

        Returns:
            Optional[List]: OHLCV data or None if error occurs
        """
        if not self._initialized:
            await self.initialize()

        try:
            if not await self.validate_trading_pair(symbol):
                logger.warning(f"Invalid or inactive trading pair: {symbol}")
                return None

            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}: {str(e)}")
            return None

    async def close(self):
        """Close the exchange connection"""
        if self._initialized and self.exchange:
            try:
                await self.exchange.close()
                self._initialized = False
                logger.info(f"Exchange {self.exchange_id} connection closed")
            except Exception as e:
                logger.error(f"Error closing exchange connection: {str(e)}")

# Create singleton instance
exchange_manager = ExchangeManager()
