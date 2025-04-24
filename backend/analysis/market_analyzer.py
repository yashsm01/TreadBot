import logging
from typing import List, Dict, Optional
from ..trader.exchange_manager import ExchangeManager
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

class MarketAnalyzer:
    def __init__(self, exchange_manager: ExchangeManager):
        """Initialize MarketAnalyzer with exchange manager"""
        self.exchange_manager = exchange_manager
        self.supported_pairs = []
        self.timeframes = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']

    async def initialize(self):
        """Initialize the market analyzer"""
        await self._update_supported_pairs()

    async def _update_supported_pairs(self):
        """Update the list of supported trading pairs"""
        try:
            self.supported_pairs = self.exchange_manager.get_all_active_pairs()
            logger.info(f"Updated supported pairs: {len(self.supported_pairs)} pairs found")
        except Exception as e:
            logger.error(f"Error updating supported pairs: {str(e)}")
            self.supported_pairs = []

    def get_supported_pairs(self) -> List[str]:
        """Get list of supported trading pairs"""
        return self.supported_pairs

    async def get_market_analysis(self, symbol: str, timeframe: str = '5m') -> Dict:
        """Get comprehensive market analysis for a symbol"""
        if not await self.exchange_manager.validate_trading_pair(symbol):
            raise ValueError(f"Invalid trading pair: {symbol}")

        if timeframe not in self.timeframes:
            raise ValueError(f"Invalid timeframe. Supported timeframes: {', '.join(self.timeframes)}")

        # Get market data
        volatility = await self.analyze_volatility(symbol, timeframe)
        market_summary = await self.get_market_summary(symbol)
        signals = await self.get_trading_signals(symbol, timeframe)

        if not all([volatility, market_summary, signals]):
            raise ValueError(f"Failed to get complete market analysis for {symbol}")

        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'volatility_metrics': volatility,
            'market_summary': market_summary,
            'trading_signals': signals,
            'timestamp': datetime.now().isoformat()
        }

    async def analyze_volatility(self, symbol: str, timeframe: str = '1h', periods: int = 24) -> Optional[Dict]:
        """Analyze price volatility for a trading pair"""
        try:
            if not await self.exchange_manager.validate_trading_pair(symbol):
                logger.warning(f"Invalid trading pair: {symbol}")
                return None

            ohlcv = await self.exchange_manager.get_ohlcv(symbol, timeframe, periods)
            if not ohlcv or len(ohlcv) < 2:
                return None

            # Convert to numpy array for calculations
            prices = np.array([candle[4] for candle in ohlcv])  # Close prices

            # Calculate metrics
            returns = np.diff(np.log(prices))
            volatility = np.std(returns) * np.sqrt(periods)
            avg_price = np.mean(prices)
            price_range = (np.max(prices) - np.min(prices)) / avg_price

            return {
                'symbol': symbol,
                'volatility': float(volatility),
                'avg_price': float(avg_price),
                'price_range': float(price_range),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error analyzing volatility for {symbol}: {str(e)}")
            return None

    async def get_market_summary(self, symbol: str) -> Optional[Dict]:
        """Get market summary for a trading pair"""
        try:
            if not await self.exchange_manager.validate_trading_pair(symbol):
                logger.warning(f"Invalid trading pair: {symbol}")
                return None

            ticker = await self.exchange_manager.get_ticker(symbol)
            if not ticker:
                return None

            # Get recent OHLCV data
            ohlcv = await self.exchange_manager.get_ohlcv(symbol, '1h', 24)
            if not ohlcv or len(ohlcv) < 24:
                return None

            # Calculate 24h metrics
            prices = np.array([candle[4] for candle in ohlcv])
            volume = np.array([candle[5] for candle in ohlcv])

            return {
                'symbol': symbol,
                'last_price': ticker['last'],
                'bid': ticker['bid'],
                'ask': ticker['ask'],
                'volume_24h': float(np.sum(volume)),
                'price_change_24h': float((prices[-1] - prices[0]) / prices[0] * 100),
                'high_24h': float(np.max(prices)),
                'low_24h': float(np.min(prices)),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting market summary for {symbol}: {str(e)}")
            return None

    async def get_trading_signals(self, symbol: str, timeframe: str = '1h') -> Optional[Dict]:
        """Get trading signals for a symbol"""
        try:
            if not await self.exchange_manager.validate_trading_pair(symbol):
                logger.warning(f"Invalid trading pair: {symbol}")
                return None

            # Get market data
            ohlcv = await self.exchange_manager.get_ohlcv(symbol, timeframe, 100)
            if not ohlcv or len(ohlcv) < 100:
                return None

            # Calculate technical indicators
            prices = np.array([candle[4] for candle in ohlcv])
            volumes = np.array([candle[5] for candle in ohlcv])

            # Simple moving averages
            sma20 = np.mean(prices[-20:])
            sma50 = np.mean(prices[-50:])

            # Volume analysis
            avg_volume = np.mean(volumes[-20:])
            current_volume = volumes[-1]

            # Price momentum
            momentum = (prices[-1] - prices[-20]) / prices[-20] * 100

            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'current_price': float(prices[-1]),
                'sma20': float(sma20),
                'sma50': float(sma50),
                'momentum': float(momentum),
                'volume_ratio': float(current_volume / avg_volume),
                'trend': 'bullish' if sma20 > sma50 else 'bearish',
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting trading signals for {symbol}: {str(e)}")
            return None
