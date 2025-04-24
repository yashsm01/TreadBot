import ccxt
import logging
from typing import Optional, Dict, List
from ..services.crypto_service import CryptoService
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class ExchangeManager:
    def __init__(self, db: Session, exchange_id: str = "binance"):
        self.exchange_id = exchange_id
        self.db = db
        self.exchange = self._initialize_exchange()
        self.crypto_service = CryptoService(self.db)

    def _initialize_exchange(self) -> ccxt.Exchange:
        """Initialize the exchange connection"""
        try:
            exchange_class = getattr(ccxt, self.exchange_id)
            exchange = exchange_class({
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot'
                }
            })
            logger.info(f"Exchange {self.exchange_id} initialized successfully")
            return exchange
        except Exception as e:
            logger.error(f"Failed to initialize exchange: {str(e)}")
            raise

    def get_all_active_pairs(self) -> List[str]:
        """Get all active trading pairs from the database"""
        return self.crypto_service.get_all_active_pairs()

    async def validate_trading_pair(self, symbol: str) -> bool:
        """Validate if a trading pair is supported and active"""
        try:
            # First check if the pair is in our database of active pairs
            if not self.crypto_service.validate_trading_pair(symbol):
                return False

            # Then verify with the exchange API that the pair is tradeable
            ticker = await self.exchange.fetch_ticker(symbol)
            return ticker is not None
        except Exception as e:
            logger.error(f"Error validating trading pair {symbol}: {str(e)}")
            return False

    async def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Get current ticker information for a symbol"""
        try:
            if not self.crypto_service.validate_trading_pair(symbol):
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

    async def get_ohlcv(self, symbol: str, timeframe: str = '1m', limit: int = 100) -> Optional[List]:
        """Get OHLCV data for a symbol"""
        try:
            if not self.crypto_service.validate_trading_pair(symbol):
                logger.warning(f"Invalid or inactive trading pair: {symbol}")
                return None

            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}: {str(e)}")
            return None
