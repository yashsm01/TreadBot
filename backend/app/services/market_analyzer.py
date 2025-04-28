from typing import Dict, Optional, List
import pandas as pd
from datetime import datetime, timedelta
from backend.app.core.logger import logger
from backend.app.core.config import settings
from binance.client import Client
import numpy as np

class MarketAnalyzer:
    def __init__(self):
        self.client = Client(settings.BINANCE_API_KEY, settings.BINANCE_API_SECRET)
        self.default_symbol = settings.DEFAULT_TRADING_PAIR

    def _format_symbol(self, symbol: str) -> str:
        """Format symbol to match Binance API requirements"""
        if not symbol:
            return self.default_symbol
        # Remove forward slash and convert to uppercase
        return symbol.replace("/", "").upper()

    def get_market_analysis(self, symbol: str = None) -> Dict:
        """Get comprehensive market analysis for a symbol"""
        symbol = self._format_symbol(symbol)
        try:
            # Get current market data
            ticker = self.client.get_ticker(symbol=symbol)

            # Get recent trades
            trades = self.client.get_recent_trades(symbol=symbol, limit=100)

            # Calculate basic metrics
            current_price = float(ticker['lastPrice'])
            price_change = float(ticker['priceChange'])
            price_change_percent = float(ticker['priceChangePercent'])

            # Calculate volume metrics
            volume_24h = float(ticker['volume'])
            quote_volume_24h = float(ticker['quoteVolume'])

            return {
                "symbol": symbol,
                "current_price": current_price,
                "price_change_24h": price_change,
                "price_change_percent_24h": price_change_percent,
                "volume_24h": volume_24h,
                "quote_volume_24h": quote_volume_24h,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            raise Exception(f"Error analyzing market for {symbol}: {str(e)}")

    def check_trade_viability(self, symbol: str, side: str, quantity: float, price: float) -> Dict:
        """Check if a trade is viable based on current market conditions"""
        symbol = self._format_symbol(symbol)
        try:
            # Get current market data
            ticker = self.client.get_ticker(symbol=symbol)
            current_price = float(ticker['lastPrice'])

            # Calculate price deviation
            price_deviation = abs(price - current_price) / current_price * 100

            # Get 24h trading volume
            volume_24h = float(ticker['volume'])

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
        """Get historical price data from Binance"""
        try:
            klines = self.client.get_klines(
                symbol=symbol.replace("/", ""),
                interval=interval,
                limit=limit
            )

            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close',
                'volume', 'close_time', 'quote_volume', 'trades',
                'taker_buy_base', 'taker_buy_quote', 'ignore'
            ])

            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            # Convert price columns to float
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)

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
            current_price = float(self.client.get_symbol_ticker(
                symbol=symbol.replace("/", "")
            )['price'])

            volatility = await self.calculate_volatility(symbol)

            # Calculate breakout levels based on volatility
            breakout_pct = volatility / (252 ** 0.5)  # Daily volatility
            upper_level = current_price * (1 + breakout_pct)
            lower_level = current_price * (1 - breakout_pct)

            return {
                "symbol": symbol,
                "strategy": strategy,
                "current_price": current_price,
                "volatility": volatility,
                "upper_level": upper_level,
                "lower_level": lower_level,
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

market_analyzer = MarketAnalyzer()
