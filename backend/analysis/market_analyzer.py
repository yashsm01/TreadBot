import logging
from typing import Dict, List, Optional
from ..services.crypto_service import CryptoService
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import ccxt

logger = logging.getLogger(__name__)

class MarketAnalyzer:
    def __init__(self, crypto_service: CryptoService):
        self.crypto_service = crypto_service
        self.exchange = ccxt.binance()
        self.timeframes = ['5m', '10m', '15m']
        self._update_supported_pairs()
        self.volatility_threshold = 0.02  # 2% threshold for volatility
        self.time_windows = {
            "5m": 12,    # 1 hour divided into 5-minute intervals
            "10m": 6,    # 1 hour divided into 10-minute intervals
            "15m": 4     # 1 hour divided into 15-minute intervals
        }

    def _update_supported_pairs(self):
        """Update supported pairs from database"""
        self.supported_pairs = self.crypto_service.get_all_active_pairs()

    async def get_market_analysis(self, symbol: str, timeframe: str) -> Dict:
        """Get market analysis for a symbol"""
        try:
            # Validate inputs
            if not self.crypto_service.validate_trading_pair(symbol):
                raise ValueError(f"Invalid trading pair: {symbol}")
            if timeframe not in self.timeframes:
                raise ValueError(f"Invalid timeframe: {timeframe}")

            # Get historical data
            historical_data = await self._get_historical_data(symbol, timeframe)

            # Calculate current price
            current_price = float(self.exchange.fetch_ticker(symbol.replace('/', ''))['last'])

            # Calculate indicators
            indicators = self._calculate_indicators(historical_data)

            # Generate signals
            signals = self._generate_signals(indicators)

            # Calculate support and resistance
            support_resistance = self._calculate_support_resistance(historical_data)

            # Calculate volatility
            volatility = self._calculate_volatility(historical_data)

            # Generate recommendation
            recommendation = self._generate_recommendation(
                current_price,
                indicators,
                signals,
                support_resistance,
                volatility
            )

            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'current_price': current_price,
                'indicators': indicators,
                'signals': signals,
                'support_resistance': support_resistance,
                'volatility': volatility,
                'recommendation': recommendation
            }

        except Exception as e:
            logger.error(f"Error in market analysis for {symbol}: {str(e)}")
            raise

    async def _get_historical_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Get historical price data"""
        try:
            # Convert timeframe to valid exchange timeframe
            exchange_timeframe = self._convert_timeframe(timeframe)

            # Fetch OHLCV data
            ohlcv = self.exchange.fetch_ohlcv(
                symbol.replace('/', ''),
                timeframe=exchange_timeframe,
                limit=100  # Last 100 candles
            )

            # Convert to DataFrame
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            return df

        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {str(e)}")
            raise

    def _convert_timeframe(self, timeframe: str) -> str:
        """Convert internal timeframe to exchange timeframe"""
        return timeframe  # For Binance, our timeframes are already compatible

    def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Calculate technical indicators"""
        try:
            close_prices = df['close'].values

            # Calculate SMA
            sma20 = self._calculate_sma(close_prices, 20)
            sma50 = self._calculate_sma(close_prices, 50)

            # Calculate RSI
            rsi = self._calculate_rsi(close_prices)

            # Calculate Bollinger Bands
            bb_middle, bb_upper, bb_lower = self._calculate_bollinger_bands(close_prices)

            return {
                'sma20': float(sma20[-1]),
                'sma50': float(sma50[-1]),
                'rsi': float(rsi[-1]),
                'bb_middle': float(bb_middle[-1]),
                'bb_upper': float(bb_upper[-1]),
                'bb_lower': float(bb_lower[-1])
            }

        except Exception as e:
            logger.error(f"Error calculating indicators: {str(e)}")
            raise

    def _calculate_sma(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calculate Simple Moving Average"""
        return pd.Series(data).rolling(window=period).mean().values

    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate Relative Strength Index"""
        deltas = np.diff(prices)
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum()/period
        down = -seed[seed < 0].sum()/period
        rs = up/down
        rsi = np.zeros_like(prices)
        rsi[:period] = 100. - 100./(1. + rs)

        for i in range(period, len(prices)):
            delta = deltas[i - 1]
            if delta > 0:
                upval = delta
                downval = 0.
            else:
                upval = 0.
                downval = -delta

            up = (up * (period - 1) + upval) / period
            down = (down * (period - 1) + downval) / period
            rs = up/down
            rsi[i] = 100. - 100./(1. + rs)

        return rsi

    def _calculate_bollinger_bands(self, prices: np.ndarray, period: int = 20, num_std: float = 2.0) -> tuple:
        """Calculate Bollinger Bands"""
        middle_band = self._calculate_sma(prices, period)
        std = pd.Series(prices).rolling(window=period).std().values
        upper_band = middle_band + (std * num_std)
        lower_band = middle_band - (std * num_std)
        return middle_band, upper_band, lower_band

    def _calculate_volatility(self, df: pd.DataFrame) -> Dict:
        """Calculate volatility metrics"""
        try:
            # Calculate daily returns
            returns = df['close'].pct_change()

            # Current volatility (last 20 periods)
            current_volatility = returns.tail(20).std()

            # Historical volatility (all available periods)
            historical_volatility = returns.std()

            return {
                'current_volatility': float(current_volatility),
                'historical_volatility': float(historical_volatility)
            }

        except Exception as e:
            logger.error(f"Error calculating volatility: {str(e)}")
            raise

    def _calculate_support_resistance(self, df: pd.DataFrame) -> Dict:
        """Calculate support and resistance levels"""
        try:
            # Use recent price action (last 50 periods)
            recent_high = df['high'].tail(50).max()
            recent_low = df['low'].tail(50).min()

            # Calculate potential support levels
            support_levels = [
                recent_low,
                recent_low * 0.99,  # 1% below recent low
                recent_low * 0.98   # 2% below recent low
            ]

            # Calculate potential resistance levels
            resistance_levels = [
                recent_high,
                recent_high * 1.01,  # 1% above recent high
                recent_high * 1.02   # 2% above recent high
            ]

            return {
                'support_levels': [float(level) for level in support_levels],
                'resistance_levels': [float(level) for level in resistance_levels]
            }

        except Exception as e:
            logger.error(f"Error calculating support/resistance: {str(e)}")
            raise

    def _generate_signals(self, indicators: Dict) -> Dict:
        """Generate trading signals based on indicators"""
        try:
            # Determine trend based on SMAs
            trend = "bullish" if indicators['sma20'] > indicators['sma50'] else "bearish"

            # RSI signals
            rsi_signal = "oversold" if indicators['rsi'] < 30 else "overbought" if indicators['rsi'] > 70 else "neutral"

            # Bollinger Bands signals
            bb_signal = "lower_band" if indicators['bb_lower'] > indicators['bb_middle'] else "upper_band" if indicators['bb_upper'] < indicators['bb_middle'] else "middle_band"

            return {
                'trend': trend,
                'rsi_signal': rsi_signal,
                'bb_signal': bb_signal
            }

        except Exception as e:
            logger.error(f"Error generating signals: {str(e)}")
            raise

    def _generate_recommendation(
        self,
        current_price: float,
        indicators: Dict,
        signals: Dict,
        support_resistance: Dict,
        volatility: Dict
    ) -> Dict:
        """Generate trading recommendation"""
        try:
            action = "hold"
            confidence = 0.5
            reason = "Market conditions are neutral"
            stop_loss = None
            target_price = None

            # Check for oversold conditions (potential buy)
            if (signals['rsi_signal'] == "oversold" and
                current_price <= indicators['bb_lower']):
                action = "buy"
                confidence = 0.8
                reason = "RSI oversold + price at BB lower band"
                stop_loss = current_price * 0.98  # 2% below entry
                target_price = current_price * 1.05  # 5% profit target

            # Check for overbought conditions (potential sell)
            elif (signals['rsi_signal'] == "overbought" and
                  current_price >= indicators['bb_upper']):
                action = "sell"
                confidence = 0.8
                reason = "RSI overbought + price at BB upper band"
                stop_loss = current_price * 1.02  # 2% above entry
                target_price = current_price * 0.95  # 5% profit target

            # Consider trend
            if signals['trend'] == "bullish":
                if action == "buy":
                    confidence += 0.1
                elif action == "sell":
                    confidence -= 0.1
            else:  # bearish trend
                if action == "sell":
                    confidence += 0.1
                elif action == "buy":
                    confidence -= 0.1

            # Adjust for volatility
            if volatility['current_volatility'] > volatility['historical_volatility']:
                confidence *= 0.9  # Reduce confidence in high volatility

            return {
                'action': action,
                'confidence': min(confidence, 1.0),  # Cap at 1.0
                'reason': reason,
                'stop_loss': float(stop_loss) if stop_loss else None,
                'target_price': float(target_price) if target_price else None
            }

        except Exception as e:
            logger.error(f"Error generating recommendation: {str(e)}")
            raise
