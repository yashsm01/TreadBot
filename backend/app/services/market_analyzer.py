from typing import Dict, Optional, List
import pandas as pd
from datetime import datetime, timedelta
import platform
import asyncio
from ..core.logger import logger
from ..core.config import settings
from ..core.exchange.exchange_manager import exchange_manager
import numpy as np

# Set event loop policy for Windows
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

class MarketAnalyzer:
    def __init__(self):
        self.default_symbol = settings.DEFAULT_TRADING_PAIR

    def _format_symbol(self, symbol: str) -> str:
        """Format symbol to match exchange API requirements"""
        if not symbol:
            return self.default_symbol

        # Ensure symbol is in correct format (e.g., "BTC/USDT")
        symbol = symbol.upper()
        if "/" not in symbol:
            if "USDT" in symbol:
                base = symbol[:-4]  # Remove USDT
                quote = symbol[-4:]  # USDT
                return f"{base}/{quote}"
        return symbol

    async def get_market_analysis(self, symbol: str = None) -> Dict:
        """
        Get market analysis for a trading pair.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT' or 'BTCUSDT')

        Returns:
            Dict: Market analysis results with error information if applicable
        """
        try:
            symbol = self._format_symbol(symbol)

            # Get current ticker data
            ticker_data = await exchange_manager.get_ticker(symbol)
            if ticker_data.get('error'):
                logger.error(f"Failed to get ticker data: {ticker_data['message']}")
                return {
                    'error': True,
                    'message': ticker_data['message'],
                    'symbol': symbol
                }

            # Get price data for technical analysis
            price_data = await self.get_price_data(symbol)
            if isinstance(price_data, dict) and price_data.get('error'):
                return price_data

            # Calculate market indicators
            volatility = await self.calculate_volatility(symbol)
            trading_signal = await self.get_trading_signal(symbol)
            market_conditions = await self.check_market_conditions(symbol)

            return {
                'error': False,
                'symbol': symbol,
                'current_price': ticker_data['last'],
                'bid': ticker_data['bid'],
                'ask': ticker_data['ask'],
                'volume_24h': ticker_data['volume'],
                'volatility': volatility,
                'trading_signal': trading_signal,
                'market_conditions': market_conditions,
                'timestamp': datetime.fromtimestamp(ticker_data['timestamp'] / 1000).isoformat()
            }
        except Exception as e:
            error_msg = f"Error performing market analysis for {symbol}: {str(e)}"
            logger.error(error_msg)
            return {
                'error': True,
                'message': error_msg,
                'symbol': symbol
            }

    async def check_trade_viability(self, symbol: str, side: str, quantity: float, price: float) -> Dict:
        """Check if a trade is viable based on current market conditions"""
        symbol = self._format_symbol(symbol)
        try:
            # Get current market data
            ticker = await self.get_market_analysis(symbol)
            current_price = ticker['current_price']

            # Calculate price deviation
            price_deviation = abs(price - current_price) / current_price * 100

            # Get 24h trading volume
            volume_24h = ticker['volume_24h']

            # Basic viability checks
            is_viable = True
            reasons = []

            # Check price deviation
            if price_deviation > 5:  # 5% deviation threshold
                is_viable = False
                reasons.append(f"Price deviation too high: {price_deviation:.2f}%")

            # Check minimum volume
            min_volume = 1000  # Example minimum volume in base currency
            if volume_24h < min_volume:
                is_viable = False
                reasons.append(f"24h volume too low: {volume_24h}")

            return {
                "is_viable": is_viable,
                "current_price": current_price,
                "price_deviation": price_deviation,
                "volume_24h": volume_24h,
                "reasons": reasons,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            raise Exception(f"Error checking trade viability: {str(e)}")

    async def get_price_data(
        self,
        symbol: str,
        interval: str = "5m",
        limit: int = 100
    ) -> pd.DataFrame:
        """Get historical price data"""
        try:
            ohlcv = await exchange_manager.get_ohlcv(symbol, timeframe=interval, limit=limit)
            if not ohlcv:
                raise Exception(f"Could not get OHLCV data for {symbol}")

            df = pd.DataFrame(ohlcv, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume'
            ])

            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            return df
        except Exception as e:
            logger.error(f"Error fetching price data: {str(e)}")
            raise

    async def calculate_volatility(
        self,
        symbol: str,
        period: int = 14
    ) -> float:
        """Calculate price volatility"""
        try:
            df = await self.get_price_data(symbol, limit=period)
            returns = df['close'].pct_change().dropna()
            volatility = returns.std() * (252 ** 0.5)  # Annualized volatility
            return float(volatility)
        except Exception as e:
            logger.error(f"Error calculating volatility: {str(e)}")
            raise

    async def get_trading_signal(
        self,
        symbol: str,
        strategy: str = "TIME_BASED_STRADDLE"
    ) -> Dict:
        """Generate trading signals based on strategy"""
        try:
            # Get current market data
            ticker = await exchange_manager.get_ticker(symbol)
            if not ticker:
                raise Exception(f"Could not get ticker data for {symbol}")
            current_price = ticker['last']

            # Get price data for technical analysis
            df = await self.get_price_data(symbol, interval="1h", limit=24)

            # Calculate volatility
            volatility = await self.calculate_volatility(symbol)

            # Calculate RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]

            # Calculate support and resistance levels using recent lows and highs
            support = df['low'].rolling(window=12).min().iloc[-1]
            resistance = df['high'].rolling(window=12).max().iloc[-1]

            # Generate primary signal based on RSI and volatility
            if rsi < 30 and volatility < 0.3:  # Low RSI and moderate volatility
                primary_signal = "Buy"
                confidence = 80
            elif rsi > 70 and volatility > 0.4:  # High RSI and high volatility
                primary_signal = "Sell"
                confidence = 75
            else:
                primary_signal = "Hold"
                confidence = 60

            # Calculate stop loss and take profit levels
            if primary_signal == "Buy":
                stop_loss = support * 0.98  # 2% below support
                take_profit = current_price * (1 + volatility)  # Use volatility for target
            elif primary_signal == "Sell":
                stop_loss = resistance * 1.02  # 2% above resistance
                take_profit = current_price * (1 - volatility)  # Use volatility for target
            else:
                stop_loss = current_price * 0.95  # Default 5% stop loss
                take_profit = current_price * 1.05  # Default 5% take profit

            return {
                "symbol": symbol,
                "strategy": strategy,
                "current_price": current_price,
                "primary_signal": primary_signal,
                "confidence": confidence,
                "support": support,
                "resistance": resistance,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "volatility": volatility * 100,  # Convert to percentage
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error generating trading signal: {str(e)}")
            raise

    async def check_market_conditions(self, symbol: str) -> Dict:
        """Check overall market conditions"""
        try:
            df = await self.get_price_data(symbol, interval="1h", limit=24)

            # Calculate basic metrics
            price_change_24h = (
                (df['close'].iloc[-1] - df['close'].iloc[0])
                / df['close'].iloc[0]
            ) * 100

            volume_24h = df['volume'].sum()
            avg_volume = df['volume'].mean()

            return {
                "symbol": symbol,
                "price_change_24h": price_change_24h,
                "volume_24h": volume_24h,
                "avg_hourly_volume": avg_volume,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error checking market conditions: {str(e)}")
            raise

    async def get_trading_pairs(self) -> List[str]:
        """Get list of available trading pairs"""
        try:
            return exchange_manager.get_all_active_pairs()
        except Exception as e:
            logger.error(f"Error getting trading pairs: {str(e)}")
            raise

market_analyzer = MarketAnalyzer()
