import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from app.core.logger import logger

@dataclass
class BreakoutSignal:
    symbol: str
    direction: str  # "UP" or "DOWN"
    price: float
    confidence: float
    volume_spike: bool
    bb_squeeze: bool
    rsi_divergence: bool
    macd_crossover: bool

class MarketAnalyzer:
    def __init__(self):
        self.bb_period = 20
        self.bb_std = 2
        self.rsi_period = 14
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.volume_threshold = 2.0  # Volume spike threshold

    def calculate_bollinger_bands(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands"""
        middle_band = prices.rolling(window=self.bb_period).mean()
        std = prices.rolling(window=self.bb_period).std()
        upper_band = middle_band + (std * self.bb_std)
        lower_band = middle_band - (std * self.bb_std)
        return upper_band, middle_band, lower_band

    def is_bb_squeeze(self, prices: pd.Series) -> bool:
        """Detect Bollinger Band squeeze"""
        upper, middle, lower = self.calculate_bollinger_bands(prices)
        band_width = (upper - lower) / middle
        recent_width = band_width.iloc[-1]
        avg_width = band_width.rolling(window=20).mean().iloc[-1]
        return recent_width < avg_width * 0.5

    def calculate_rsi(self, prices: pd.Series) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def detect_rsi_divergence(self, prices: pd.Series, rsi: pd.Series) -> bool:
        """Detect RSI divergence"""
        price_trend = prices.iloc[-5:].pct_change().mean()
        rsi_trend = rsi.iloc[-5:].diff().mean()
        return (price_trend > 0 and rsi_trend < 0) or (price_trend < 0 and rsi_trend > 0)

    def calculate_macd(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """Calculate MACD indicator"""
        exp1 = prices.ewm(span=self.macd_fast).mean()
        exp2 = prices.ewm(span=self.macd_slow).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=self.macd_signal).mean()
        return macd, signal

    def detect_volume_spike(self, volume: pd.Series) -> bool:
        """Detect volume spike"""
        avg_volume = volume.rolling(window=20).mean()
        return volume.iloc[-1] > avg_volume.iloc[-1] * self.volume_threshold

    def analyze_breakout(self,
                        symbol: str,
                        prices: pd.Series,
                        volume: pd.Series) -> Optional[BreakoutSignal]:
        """
        Analyze price action for breakout signals
        Returns a BreakoutSignal if conditions are met, None otherwise
        """
        try:
            # Calculate indicators
            upper_bb, middle_bb, lower_bb = self.calculate_bollinger_bands(prices)
            rsi = self.calculate_rsi(prices)
            macd, signal = self.calculate_macd(prices)

            # Check for squeeze
            bb_squeeze = self.is_bb_squeeze(prices)
            if not bb_squeeze:
                return None

            # Check for volume spike
            volume_spike = self.detect_volume_spike(volume)

            # Check for RSI divergence
            rsi_divergence = self.detect_rsi_divergence(prices, rsi)

            # Check for MACD crossover
            macd_crossover = (macd.iloc[-2] < signal.iloc[-2] and
                            macd.iloc[-1] > signal.iloc[-1]) or \
                           (macd.iloc[-2] > signal.iloc[-2] and
                            macd.iloc[-1] < signal.iloc[-1])

            current_price = prices.iloc[-1]

            # Determine breakout direction and confidence
            if current_price > upper_bb.iloc[-1]:
                direction = "UP"
                confidence = min(1.0, (current_price - upper_bb.iloc[-1]) /
                               (upper_bb.iloc[-1] - middle_bb.iloc[-1]))
            elif current_price < lower_bb.iloc[-1]:
                direction = "DOWN"
                confidence = min(1.0, (lower_bb.iloc[-1] - current_price) /
                               (middle_bb.iloc[-1] - lower_bb.iloc[-1]))
            else:
                return None

            # Create breakout signal
            signal = BreakoutSignal(
                symbol=symbol,
                direction=direction,
                price=current_price,
                confidence=confidence,
                volume_spike=volume_spike,
                bb_squeeze=bb_squeeze,
                rsi_divergence=rsi_divergence,
                macd_crossover=macd_crossover
            )

            logger.info(f"Breakout signal detected for {symbol}: {direction} at {current_price}")
            return signal

        except Exception as e:
            logger.error(f"Error in breakout analysis: {str(e)}")
            return None

market_analyzer = MarketAnalyzer()
