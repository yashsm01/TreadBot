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

    @staticmethod
    def validate_input_data(symbol: str, prices: pd.Series, volume: pd.Series) -> Tuple[bool, str]:
        """Validate input data for analysis"""
        try:
            if not isinstance(symbol, str) or not symbol:
                logger.warning(f"Invalid symbol provided: {symbol}")
                return False, "Invalid symbol provided"

            if not isinstance(prices, pd.Series) or prices.empty:
                logger.warning("Invalid or empty price data")
                return False, "Invalid or empty price data"

            if not isinstance(volume, pd.Series) or volume.empty:
                logger.warning("Invalid or empty volume data")
                return False, "Invalid or empty volume data"

            # Log data statistics
            logger.info(f"""
            Data Validation Statistics:
            Symbol: {symbol}
            Price Data Points: {len(prices)}
            Price Range: {prices.min():.2f} - {prices.max():.2f}
            Volume Data Points: {len(volume)}
            Volume Range: {volume.min():.2f} - {volume.max():.2f}
            """)

            if len(prices) < 20:
                logger.warning(f"Insufficient price data points: {len(prices)} < 20")
                return False, f"Insufficient price data (minimum 20 periods required, got {len(prices)})"

            if prices.isnull().any():
                null_count = prices.isnull().sum()
                logger.warning(f"Price data contains {null_count} missing values")
                return False, f"Price data contains {null_count} missing values"

            if volume.isnull().any():
                null_count = volume.isnull().sum()
                logger.warning(f"Volume data contains {null_count} missing values")
                return False, f"Volume data contains {null_count} missing values"

            if (prices <= 0).any():
                invalid_count = (prices <= 0).sum()
                logger.warning(f"Price data contains {invalid_count} non-positive values")
                return False, f"Price data contains {invalid_count} invalid values (must be > 0)"

            if (volume < 0).any():
                invalid_count = (volume < 0).sum()
                logger.warning(f"Volume data contains {invalid_count} negative values")
                return False, f"Volume data contains {invalid_count} invalid values (must be >= 0)"

            logger.info(f"Data validation successful for {symbol}")
            return True, "Validation successful"
        except Exception as e:
            logger.error(f"Validation error: {str(e)}")
            return False, f"Validation error: {str(e)}"

    @staticmethod
    def calculate_bollinger_bands(prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Bollinger Bands
        Returns: (upper_band, middle_band, lower_band)
        """
        try:
            bb_period = 20  # bb period means how many days to calculate the moving average and standard deviation
            bb_std = 2  # bb std means how many standard deviations to add to the moving average

            # Calculate middle band (Simple Moving Average)
            middle_band = prices.rolling(window=bb_period, min_periods=1).mean()

            # Calculate standard deviation
            std = prices.rolling(window=bb_period, min_periods=1).std()

            # Calculate upper and lower bands
            upper_band = middle_band + (std * bb_std)
            lower_band = middle_band - (std * bb_std)

            # Log the calculations for debugging
            logger.debug(f"""
            Bollinger Bands Calculation:
            Latest Values:
            Upper Band: {upper_band.iloc[-1]:.2f}
            Middle Band: {middle_band.iloc[-1]:.2f}
            Lower Band: {lower_band.iloc[-1]:.2f}
            Standard Deviation: {std.iloc[-1]:.2f}
            """)

            # Check for NaN values in the latest data point
            if pd.isna(upper_band.iloc[-1]) or pd.isna(middle_band.iloc[-1]) or pd.isna(lower_band.iloc[-1]):
                logger.warning("NaN values detected in Bollinger Bands calculation")
                raise ValueError("Invalid Bollinger Bands calculation - NaN values detected")

            return upper_band, middle_band, lower_band

        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {str(e)}")
            raise

    @staticmethod
    def is_bb_squeeze(prices: pd.Series) -> Tuple[bool, float]:
        """Detect Bollinger Band squeeze"""
        try:
            upper, middle, lower = MarketAnalyzer.calculate_bollinger_bands(prices)

            # Calculate bandwidth
            band_width = (upper - lower) / middle
            recent_width = float(band_width.iloc[-1])
            avg_width = float(band_width.rolling(window=20, min_periods=1).mean().iloc[-1])

            # Calculate squeeze intensity
            squeeze_intensity = float(avg_width / recent_width if recent_width > 0 else 0)
            is_squeeze = bool(recent_width < avg_width * 0.5)

            logger.debug(f"""
            BB Squeeze Analysis:
            Recent Band Width: {recent_width:.4f}
            Average Band Width: {avg_width:.4f}
            Squeeze Intensity: {squeeze_intensity:.4f}
            Is Squeeze: {is_squeeze}
            """)

            return is_squeeze, squeeze_intensity

        except Exception as e:
            logger.error(f"Error in BB squeeze calculation: {str(e)}")
            raise

    @staticmethod
    def calculate_rsi(prices: pd.Series) -> pd.Series:
        """Calculate RSI indicator"""
        rsi_period = 14
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def detect_rsi_divergence(prices: pd.Series, rsi: pd.Series) -> Tuple[bool, float]:
        """Detect RSI divergence"""
        price_trend = float(prices.iloc[-5:].pct_change().mean())
        rsi_trend = float(rsi.iloc[-5:].diff().mean())
        divergence_strength = abs(price_trend - rsi_trend)
        is_divergence = bool((price_trend > 0 and rsi_trend < 0) or (price_trend < 0 and rsi_trend > 0))
        logger.debug(f"RSI Divergence: {is_divergence}, Strength: {divergence_strength:.4f}")
        return is_divergence, divergence_strength

    @staticmethod
    def calculate_macd(prices: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """Calculate MACD indicator"""
        macd_fast = 12
        macd_slow = 26
        macd_signal = 9
        exp1 = prices.ewm(span=macd_fast).mean()
        exp2 = prices.ewm(span=macd_slow).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=macd_signal).mean()
        return macd, signal

    @staticmethod
    def detect_volume_spike(volume: pd.Series) -> Tuple[bool, float]:
        """Detect volume spike"""
        volume_threshold = 2.0
        avg_volume = volume.rolling(window=20).mean()
        volume_ratio = float(volume.iloc[-1] / avg_volume.iloc[-1] if avg_volume.iloc[-1] > 0 else 0)
        is_spike = bool(volume_ratio > volume_threshold)
        logger.debug(f"Volume Spike: {is_spike}, Ratio: {volume_ratio:.2f}")
        return is_spike, volume_ratio

    @staticmethod
    async def analyze_breakout(
        symbol: str,
        prices: pd.Series,
        volume: pd.Series
    ) -> Dict:
        """
        Analyze price action for breakout signals
        Returns a detailed analysis including breakout signal if conditions are met
        """
        try:
            logger.info(f"Starting breakout analysis for {symbol}")

            # Validate input data
            is_valid, validation_message = MarketAnalyzer.validate_input_data(symbol, prices, volume)
            if not is_valid:
                return {
                    "has_signal": False,
                    "message": validation_message,
                    "validation_error": True
                }

            # Calculate indicators
            upper_bb, middle_bb, lower_bb = MarketAnalyzer.calculate_bollinger_bands(prices)
            rsi = MarketAnalyzer.calculate_rsi(prices)
            macd, signal = MarketAnalyzer.calculate_macd(prices)

            # Check for squeeze with intensity
            bb_squeeze, squeeze_intensity = MarketAnalyzer.is_bb_squeeze(prices)

            # Check for volume spike with ratio
            volume_spike, volume_ratio = MarketAnalyzer.detect_volume_spike(volume)

            # Check for RSI divergence with strength
            rsi_divergence, divergence_strength = MarketAnalyzer.detect_rsi_divergence(prices, rsi)

            # Check for MACD crossover
            macd_crossover = bool(
                (macd.iloc[-2] < signal.iloc[-2] and macd.iloc[-1] > signal.iloc[-1]) or
                (macd.iloc[-2] > signal.iloc[-2] and macd.iloc[-1] < signal.iloc[-1])
            )

            current_price = float(prices.iloc[-1])
            current_rsi = float(rsi.iloc[-1])

            # Calculate market conditions
            market_conditions = {
                "bb_squeeze": {
                    "active": bool(bb_squeeze),
                    "intensity": float(squeeze_intensity)
                },
                "volume_spike": {
                    "active": bool(volume_spike),
                    "ratio": float(volume_ratio)
                },
                "rsi_divergence": {
                    "active": bool(rsi_divergence),
                    "strength": float(divergence_strength)
                },
                "macd_crossover": bool(macd_crossover),
                "current_rsi": float(current_rsi),
                "current_price": float(current_price)
            }

            logger.info(f"Market conditions for {symbol}: {market_conditions}")

            # Determine breakout direction and confidence
            if current_price > upper_bb.iloc[-1]:
                direction = "UP"
                confidence = float(min(1.0, (current_price - upper_bb.iloc[-1]) /
                               (upper_bb.iloc[-1] - middle_bb.iloc[-1])))

                signal = BreakoutSignal(
                    symbol=symbol,
                    direction=direction,
                    price=current_price,
                    confidence=confidence,
                    volume_spike=bool(volume_spike),
                    bb_squeeze=bool(bb_squeeze),
                    rsi_divergence=bool(rsi_divergence),
                    macd_crossover=bool(macd_crossover)
                )

                logger.info(f"Upward breakout detected for {symbol} at {current_price}")
                return {
                    "has_signal": True,
                    "signal": signal,
                    "market_conditions": market_conditions,
                    "message": "Upward breakout detected"
                }

            elif current_price < lower_bb.iloc[-1]:
                direction = "DOWN"
                confidence = float(min(1.0, (lower_bb.iloc[-1] - current_price) /
                               (middle_bb.iloc[-1] - lower_bb.iloc[-1])))

                signal = BreakoutSignal(
                    symbol=symbol,
                    direction=direction,
                    price=current_price,
                    confidence=confidence,
                    volume_spike=bool(volume_spike),
                    bb_squeeze=bool(bb_squeeze),
                    rsi_divergence=bool(rsi_divergence),
                    macd_crossover=bool(macd_crossover)
                )

                logger.info(f"Downward breakout detected for {symbol} at {current_price}")
                return {
                    "has_signal": True,
                    "signal": signal,
                    "market_conditions": market_conditions,
                    "message": "Downward breakout detected"
                }

            logger.info(f"No breakout signals detected for {symbol}")
            return {
                "has_signal": False,
                "market_conditions": market_conditions,
                "message": "No significant breakout signals detected",
                "reason": "Price within Bollinger Bands"
            }

        except Exception as e:
            logger.error(f"Error in breakout analysis for {symbol}: {str(e)}")
            return {
                "has_signal": False,
                "message": f"Error in analysis: {str(e)}",
                "error": True
            }
