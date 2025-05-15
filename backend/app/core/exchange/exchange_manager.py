import ccxt.async_support as ccxt
import logging
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from ...services.crypto_service import crypto_service
from ...core.config import settings
from ...core.logger import logger
from datetime import datetime

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

    async def fetch_ticker_fallback(self, symbol: str) -> Dict:
        """
        Custom implementation of fetch_ticker in case the exchange doesn't provide it directly.

        Args:
            symbol: Trading pair symbol

        Returns:
            Dict: Ticker information
        """
        try:
            # Try different methods to get ticker data
            # Method 1: Try fetch_ticker directly
            if hasattr(self.exchange, 'fetch_ticker') and callable(getattr(self.exchange, 'fetch_ticker')):
                return await self.exchange.fetch_ticker(symbol)

            # Method 2: Try to use fetch_tickers to get a single ticker
            if hasattr(self.exchange, 'fetch_tickers') and callable(getattr(self.exchange, 'fetch_tickers')):
                tickers = await self.exchange.fetch_tickers([symbol])
                if symbol in tickers:
                    return tickers[symbol]

            # Method 3: Try to get from recent trades
            if hasattr(self.exchange, 'fetch_trades') and callable(getattr(self.exchange, 'fetch_trades')):
                trades = await self.exchange.fetch_trades(symbol, limit=1)
                if trades and len(trades) > 0:
                    return {
                        'symbol': symbol,
                        'last': trades[0]['price'],
                        'bid': trades[0]['price'],
                        'ask': trades[0]['price'],
                        'baseVolume': 0,
                        'timestamp': trades[0]['timestamp']
                    }

            # Method 4: Use order book
            if hasattr(self.exchange, 'fetch_order_book') and callable(getattr(self.exchange, 'fetch_order_book')):
                order_book = await self.exchange.fetch_order_book(symbol)
                if order_book and 'bids' in order_book and 'asks' in order_book:
                    bid = order_book['bids'][0][0] if order_book['bids'] else 0
                    ask = order_book['asks'][0][0] if order_book['asks'] else 0
                    last = (bid + ask) / 2 if bid and ask else 0
                    return {
                        'symbol': symbol,
                        'last': last,
                        'bid': bid,
                        'ask': ask,
                        'baseVolume': 0,
                        'timestamp': int(datetime.now().timestamp() * 1000)
                    }

            # If we get here, all methods failed
            logger.error(f"Could not get ticker data for {symbol} using any available method")
            raise Exception(f"No ticker data available for {symbol}")

        except Exception as e:
            logger.error(f"Error in fetch_ticker_fallback for {symbol}: {str(e)}")
            raise

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
            formatted_symbol = symbol
            if '/' not in symbol:
                # Handle different symbol formats
                if symbol.endswith('USDT'):
                    # Something like BTCUSDT
                    formatted_symbol = f"{symbol[:-4]}/USDT"
                elif 'USDT' in symbol:
                    # Something like BTC-USDT or BTC_USDT
                    formatted_symbol = symbol.replace('-', '/').replace('_', '/')
                else:
                    # Try to infer format
                    for quote in ['USDT', 'BTC', 'ETH', 'BNB']:
                        if quote in symbol:
                            base = symbol.replace(quote, '')
                            formatted_symbol = f"{base}/{quote}"
                            break

            logger.info(f"Getting ticker for symbol: {symbol}, formatted as: {formatted_symbol}")

            # Use our fallback implementation that tries multiple methods
            ticker = await self.fetch_ticker_fallback(formatted_symbol)

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
                'last': ticker.get('last', 0),
                'bid': ticker.get('bid', 0),
                'ask': ticker.get('ask', 0),
                'volume': ticker.get('baseVolume', 0),
                'timestamp': ticker.get('timestamp', 0)
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
