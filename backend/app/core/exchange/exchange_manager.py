import ccxt.async_support as ccxt
import logging
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from ...services.crypto_service import crypto_service
from ...core.config import settings
from ...core.logger import logger

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
                    'defaultType': 'spot',
                    'adjustForTimeDifference': True,
                    'recvWindow': 60000
                },
                'timeout': 30000,
                'apiKey': settings.BINANCE_API_KEY,
                'secret': settings.BINANCE_SECRET_KEY
            })
            await self.exchange.load_markets()
            self._initialized = True
            logger.info(f"Exchange {self.exchange_id} initialized successfully")
        except ccxt.NetworkError as e:
            logger.error(f"Network error initializing exchange: {str(e)}")
            raise
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error during initialization: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error initializing exchange: {str(e)}")
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

        Raises:
            ccxt.NetworkError: If there's a network connectivity issue
            ccxt.ExchangeError: If the exchange returns an error
            Exception: For unexpected errors
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Format symbol if needed (e.g., convert BTCUSDT to BTC/USDT)
            if '/' not in symbol:
                formatted_symbol = f"{symbol[:-4]}/{symbol[-4:]}" if symbol.endswith('USDT') else symbol
            else:
                formatted_symbol = symbol

            # Validate the trading pair
            if not await self.validate_trading_pair(formatted_symbol):
                logger.warning(f"Invalid or inactive trading pair: {formatted_symbol}")
                return {
                    'error': True,
                    'message': f"Invalid or inactive trading pair: {formatted_symbol}",
                    'symbol': formatted_symbol
                }

            ticker = await self.exchange.fetch_ticker(formatted_symbol)
            if not ticker:
                logger.warning(f"No ticker data available for {formatted_symbol}")
                return {
                    'error': True,
                    'message': f"No ticker data available for {formatted_symbol}",
                    'symbol': formatted_symbol
                }

            return {
                'error': False,
                'symbol': formatted_symbol,
                'last': ticker['last'],
                'bid': ticker['bid'],
                'ask': ticker['ask'],
                'volume': ticker['baseVolume'],
                'timestamp': ticker['timestamp']
            }
        except ccxt.NetworkError as e:
            error_msg = f"Network error fetching ticker for {symbol}: {str(e)}"
            logger.error(error_msg)
            return {
                'error': True,
                'message': error_msg,
                'symbol': symbol,
                'error_type': 'network'
            }
        except ccxt.ExchangeError as e:
            error_msg = f"Exchange error fetching ticker for {symbol}: {str(e)}"
            logger.error(error_msg)
            return {
                'error': True,
                'message': error_msg,
                'symbol': symbol,
                'error_type': 'exchange'
            }
        except Exception as e:
            error_msg = f"Unexpected error fetching ticker for {symbol}: {str(e)}"
            logger.error(error_msg)
            return {
                'error': True,
                'message': error_msg,
                'symbol': symbol,
                'error_type': 'unknown'
            }

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
