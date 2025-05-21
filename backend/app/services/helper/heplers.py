import pytz
from datetime import datetime
import uuid
import numpy as np
from typing import List, Tuple, Dict, Any, Optional
from app.core.logger import logger

class Helpers:
  def generate_transaction_id(self) -> str:
    return str(uuid.uuid4())

  def convert_to_indian_standard_time(self, dt: datetime) -> datetime:
    return dt.astimezone(pytz.timezone('Asia/Kolkata'))

  def convert_to_utc(self, dt: datetime) -> datetime:
    return dt.astimezone(pytz.timezone('UTC'))

  def get_current_ist_for_db(self) -> datetime:
    """
    Returns current time in IST but as a naive datetime (no timezone info)
    for storage in database columns defined as TIMESTAMP WITHOUT TIME ZONE
    """
    ist_time = datetime.utcnow().astimezone(pytz.timezone('Asia/Kolkata'))
    return ist_time.replace(tzinfo=None)  # Strip timezone info for DB storage

  def calculate_dynamic_profit_threshold(self, price_history: List[float], symbol: str, multiplier: float = 1.0) -> Tuple[float, float, float]:
    """
    Calculate dynamic profit thresholds based on price volatility

    Args:
        price_history: List of historical prices
        symbol: Trading symbol for logging
        multiplier: Adjustment multiplier for threshold sensitivity (lower values = more sensitive)

    Returns:
        Tuple of (small, medium, large) threshold values
    """
    try:
        if not price_history or len(price_history) < 2:
            logger.warning(f"Insufficient price data for {symbol}. Using default thresholds.")
            return 0.01 * multiplier, 0.025 * multiplier, 0.04 * multiplier

        prices = np.array(price_history)
        std_dev = np.std(prices)
        avg_price = np.mean(prices)

        # Calculate price range as percentage
        price_range_pct = (np.max(prices) - np.min(prices)) / avg_price

        # Calculate percentage returns for volatility assessment
        returns = np.diff(prices) / prices[:-1]
        returns_volatility = np.std(returns)

        # Combine multiple metrics for better volatility assessment
        # Volatility as a ratio (adjusted for intraday)
        volatility_ratio = max(std_dev / avg_price, returns_volatility * 10)

        # Get the asset's typical intraday price movement as a minimum baseline
        min_intraday_move = max(0.005, price_range_pct * 0.2)  # At least 0.5%

        # Scale thresholds accordingly with higher minimums for intraday trading
        threshold_small = max(0.008, min_intraday_move, volatility_ratio * 0.6) * multiplier  # Apply multiplier
        threshold_medium = max(0.018, min_intraday_move * 2, volatility_ratio * 1.4) * multiplier  # Apply multiplier
        threshold_large = max(0.03, min_intraday_move * 3, volatility_ratio * 2.2) * multiplier  # Apply multiplier

        logger.info(f"Dynamic thresholds for {symbol} (multiplier={multiplier}): small={threshold_small:.4f}, medium={threshold_medium:.4f}, large={threshold_large:.4f}, volatility={volatility_ratio:.4f}")
        return threshold_small, threshold_medium, threshold_large
    except Exception as e:
        logger.error(f"Error calculating dynamic profit thresholds: {str(e)}")
        # Fallback to default values
        return 0.01 * multiplier, 0.025 * multiplier, 0.04 * multiplier

  def dynamic_consecutive_increase_threshold(self, price_changes: List[float], symbol: str) -> int:
    """
    Calculate dynamic threshold for consecutive price increases based on volatility

    Args:
        price_changes: List of price changes between periods
        symbol: Trading symbol for logging

    Returns:
        Threshold count for consecutive increases
    """
    try:
        if len(price_changes) == 0:
            return 3  # Default value

        # Calculate relative price changes (as percentages)
        if not hasattr(price_changes, 'mean'):  # Check if it's not a numpy array
            price_changes = np.array(price_changes)

        # Calculate average price for context if not a numpy array
        avg_price = np.mean(np.abs(price_changes)) if hasattr(price_changes, 'mean') else sum(abs(p) for p in price_changes) / len(price_changes)

        # Calculate normalized percentage changes if possible
        # This helps in getting more meaningful values for intraday trading
        pct_changes = price_changes if avg_price == 0 else price_changes / avg_price * 100

        # Calculate the 75th percentile of absolute changes to better represent significant moves
        # This is more robust than the average for intraday trading
        significant_change = np.percentile(np.abs(pct_changes), 75) if len(pct_changes) > 4 else np.mean(np.abs(pct_changes))

        # More suitable thresholds for intraday trading
        if significant_change < 0.05:  # Extremely low volatility (likely a stablecoin)
            threshold = 6  # Need more confirmation for low volatility assets
        elif significant_change < 0.2:  # Low volatility
            threshold = 4  # Still need good confirmation
        elif significant_change < 0.5:  # Medium volatility
            threshold = 3  # Standard value
        else:  # High volatility
            threshold = 2  # High volatility needs fewer confirmations

        logger.info(f"Dynamic consecutive threshold for {symbol}: {threshold}, significant_change={significant_change:.5f}")
        return threshold
    except Exception as e:
        logger.error(f"Error calculating consecutive increase threshold: {str(e)}")
        return 3  # Default value

  def calculate_volatility_threshold(self, prices: List[float], symbol: str) -> float:
    """
    Calculate dynamic volatility threshold based on historical price data

    Args:
        prices: List of historical prices
        symbol: Trading symbol for logging

    Returns:
        Volatility threshold as float
    """
    try:
        if len(prices) < 2:
            return 0.02  # Default value more suitable for intraday

        # Convert to numpy array if not already
        if not hasattr(prices, 'mean'):  # Check if it's not a numpy array
            prices = np.array(prices)

        # Calculate returns as percentages (more meaningful than price differences)
        returns = np.diff(prices) / prices[:-1]

        # Use a combination of standard deviation and range for better measure
        std = np.std(returns)
        price_range = (np.max(prices) - np.min(prices)) / np.mean(prices)

        # Calculate typical intraday volatility measures
        atr_equivalent = price_range / len(prices) * 5  # Approximation of ATR concept

        # Combined volatility measure
        combined_volatility = max(std, atr_equivalent)

        # Apply scaling factor to make it usable as a threshold
        # Higher minimum for intraday trading
        threshold = max(0.015, combined_volatility * 1.8)  # Minimum 1.5%

        logger.info(f"Dynamic volatility threshold for {symbol}: {threshold:.4f}, std={std:.4f}, range={price_range:.4f}")
        return threshold
    except Exception as e:
        logger.error(f"Error calculating volatility threshold: {str(e)}")
        return 0.02  # Default value

  def find_support_resistance_levels(self, highs: List[float], lows: List[float], current_price: float, num_levels: int = 3) -> Tuple[List[float], List[float]]:
    """
    Identify key support and resistance levels from historical price data

    Args:
        highs: List of historical high prices
        lows: List of historical low prices
        current_price: Current price of the asset
        num_levels: Number of support/resistance levels to identify

    Returns:
        Tuple of (support_levels, resistance_levels) lists
    """
    try:
        if len(highs) < 10 or len(lows) < 10:
            # Not enough data, return simple levels
            return [current_price * 0.99, current_price * 0.97, current_price * 0.95], [current_price * 1.01, current_price * 1.03, current_price * 1.05]

        # Convert to numpy arrays
        highs_array = np.array(highs)
        lows_array = np.array(lows)

        # Find potential resistance levels (price peaks)
        resistance_candidates = []
        for i in range(1, len(highs_array) - 1):
            if highs_array[i] > highs_array[i-1] and highs_array[i] > highs_array[i+1]:
                resistance_candidates.append(highs_array[i])

        # Find potential support levels (price troughs)
        support_candidates = []
        for i in range(1, len(lows_array) - 1):
            if lows_array[i] < lows_array[i-1] and lows_array[i] < lows_array[i+1]:
                support_candidates.append(lows_array[i])

        # If no clear peaks/troughs, use percentiles
        if len(resistance_candidates) < num_levels:
            percentiles = np.linspace(70, 95, num_levels)
            resistance_candidates = [np.percentile(highs_array, p) for p in percentiles]

        if len(support_candidates) < num_levels:
            percentiles = np.linspace(5, 30, num_levels)
            support_candidates = [np.percentile(lows_array, p) for p in percentiles]

        # Cluster nearby levels and get most significant ones
        support_levels = self._cluster_price_levels(support_candidates, current_price, num_levels, below_current=True)
        resistance_levels = self._cluster_price_levels(resistance_candidates, current_price, num_levels, below_current=False)

        logger.info(f"Support levels: {support_levels}, Resistance levels: {resistance_levels}")
        return support_levels, resistance_levels
    except Exception as e:
        logger.error(f"Error finding support/resistance levels: {str(e)}")
        # Return default levels based on current price
        return [current_price * 0.99, current_price * 0.97, current_price * 0.95], [current_price * 1.01, current_price * 1.03, current_price * 1.05]

  def _cluster_price_levels(self, level_candidates: List[float], current_price: float, num_levels: int, below_current: bool) -> List[float]:
    """
    Helper method to cluster nearby price levels and select the most significant ones

    Args:
        level_candidates: List of candidate price levels
        current_price: Current price of the asset
        num_levels: Number of levels to return
        below_current: Whether to find levels below current price (True) or above (False)

    Returns:
        List of clustered price levels
    """
    try:
        if not level_candidates:
            # No candidates, return default levels
            if below_current:
                return [current_price * (1 - 0.01 * i) for i in range(1, num_levels + 1)]
            else:
                return [current_price * (1 + 0.01 * i) for i in range(1, num_levels + 1)]

        # Filter levels based on current price
        if below_current:
            filtered_levels = [lvl for lvl in level_candidates if lvl < current_price]
        else:
            filtered_levels = [lvl for lvl in level_candidates if lvl > current_price]

        # If no levels found after filtering, use default
        if not filtered_levels:
            if below_current:
                return [current_price * (1 - 0.01 * i) for i in range(1, num_levels + 1)]
            else:
                return [current_price * (1 + 0.01 * i) for i in range(1, num_levels + 1)]

        # Sort the filtered levels
        if below_current:
            filtered_levels.sort(reverse=True)  # Descending for support (closest to current price first)
        else:
            filtered_levels.sort()  # Ascending for resistance (closest to current price first)

        # Limit to requested number of levels
        return filtered_levels[:num_levels]
    except Exception as e:
        logger.error(f"Error clustering price levels: {str(e)}")
        # Return default levels
        if below_current:
            return [current_price * (1 - 0.01 * i) for i in range(1, num_levels + 1)]
        else:
            return [current_price * (1 + 0.01 * i) for i in range(1, num_levels + 1)]

  def analyze_volume_profile(self, prices: List[float], volumes: List[float]) -> str:
    """
    Analyze trading volume patterns to detect accumulation or distribution phases

    Args:
        prices: List of historical prices
        volumes: List of corresponding trading volumes

    Returns:
        Volume profile description as string ("accumulation", "distribution", or "neutral")
    """
    try:
        if len(prices) < 5 or len(volumes) < 5:
            return "neutral"

        # Convert to numpy arrays
        prices_array = np.array(prices)
        volumes_array = np.array(volumes)

        # Calculate price changes
        price_changes = np.diff(prices_array)

        # Check if arrays have matching lengths for the analysis below
        if len(price_changes) != len(volumes_array[1:]):
            # Adjust volumes array to match price_changes length
            volumes_analysis = volumes_array[1:len(price_changes)+1]
        else:
            volumes_analysis = volumes_array[1:]

        # Calculate volume-weighted price changes
        volume_weighted_changes = price_changes * volumes_analysis

        # Calculate up-volume and down-volume
        up_volume = sum(volumes_analysis[price_changes > 0])
        down_volume = sum(volumes_analysis[price_changes < 0])

        # Calculate average volume
        avg_volume = np.mean(volumes_array)

        # Calculate recent volume trend (last 30% of data)
        recent_idx = int(len(volumes_array) * 0.7)
        recent_volumes = volumes_array[recent_idx:]
        recent_prices = prices_array[recent_idx:]
        recent_avg_volume = np.mean(recent_volumes) if len(recent_volumes) > 0 else avg_volume

        # Determine if we have accumulation or distribution
        # Accumulation: Rising prices on higher volume or falling prices on lower volume
        # Distribution: Rising prices on lower volume or falling prices on higher volume
        if recent_avg_volume > avg_volume * 1.2:
            # Higher than average recent volume
            if np.mean(recent_prices) > np.mean(prices_array[:recent_idx]):
                # Rising prices on higher volume = accumulation
                return "accumulation"
            else:
                # Falling prices on higher volume = distribution
                return "distribution"
        elif recent_avg_volume < avg_volume * 0.8:
            # Lower than average recent volume
            if np.mean(recent_prices) < np.mean(prices_array[:recent_idx]):
                # Falling prices on lower volume = potential accumulation
                return "accumulation"
            else:
                # Rising prices on lower volume = potential distribution
                return "distribution"
        elif up_volume > down_volume * 1.5:
            # Significantly more up-volume than down-volume = accumulation
            return "accumulation"
        elif down_volume > up_volume * 1.5:
            # Significantly more down-volume than up-volume = distribution
            return "distribution"
        else:
            # No clear pattern
            return "neutral"
    except Exception as e:
        logger.error(f"Error analyzing volume profile: {str(e)}")
        return "neutral"

  def detect_intraday_pattern(self, open_prices: List[float], high_prices: List[float],
                            low_prices: List[float], close_prices: List[float],
                            volumes: List[float]) -> str:
    """
    Detect common chart patterns for intraday trading

    Args:
        open_prices: List of opening prices
        high_prices: List of high prices
        low_prices: List of low prices
        close_prices: List of closing prices
        volumes: List of trading volumes

    Returns:
        Pattern identification as string
    """
    try:
        if len(close_prices) < 20:  # Need sufficient bars for pattern recognition
            return "insufficient_data"

        # Convert to numpy arrays for easier manipulation
        opens = np.array(open_prices)
        highs = np.array(high_prices)
        lows = np.array(low_prices)
        closes = np.array(close_prices)
        volumes = np.array(volumes)

        # Calculate basic indicators
        price_range = highs - lows
        body_sizes = np.abs(closes - opens)

        # Simple moving averages (5 and 20 period)
        sma5 = np.convolve(closes, np.ones(5)/5, mode='valid')
        sma20 = np.convolve(closes, np.ones(20)/20, mode='valid')

        # Moving average of volume (10 period)
        vol_ma10 = np.convolve(volumes, np.ones(10)/10, mode='valid')

        # Focus on recent price action (last 20-30 bars)
        recent_highs = highs[-30:]
        recent_lows = lows[-30:]
        recent_closes = closes[-30:]

        # Find local maxima and minima
        peaks = []
        troughs = []

        for i in range(2, len(recent_closes) - 2):
            # Local maxima (potential resistance)
            if recent_highs[i] > recent_highs[i-1] and recent_highs[i] > recent_highs[i-2] and \
               recent_highs[i] > recent_highs[i+1] and recent_highs[i] > recent_highs[i+2]:
                peaks.append((i, recent_highs[i]))

            # Local minima (potential support)
            if recent_lows[i] < recent_lows[i-1] and recent_lows[i] < recent_lows[i-2] and \
               recent_lows[i] < recent_lows[i+1] and recent_lows[i] < recent_lows[i+2]:
                troughs.append((i, recent_lows[i]))

        # Double bottom pattern
        if len(troughs) >= 2:
            # Check last two troughs
            if len(troughs) >= 2 and abs(troughs[-1][1] - troughs[-2][1]) / troughs[-2][1] < 0.03:
                # Two almost equal lows
                if troughs[-1][0] - troughs[-2][0] >= 5:  # At least 5 bars apart
                    # Check if there's a higher price between the troughs
                    between_idx = range(troughs[-2][0] + 1, troughs[-1][0])
                    if any(recent_closes[i] > recent_closes[troughs[-2][0]] * 1.02 for i in between_idx):
                        return "double_bottom"

        # Double top pattern
        if len(peaks) >= 2:
            # Check last two peaks
            if len(peaks) >= 2 and abs(peaks[-1][1] - peaks[-2][1]) / peaks[-2][1] < 0.03:
                # Two almost equal highs
                if peaks[-1][0] - peaks[-2][0] >= 5:  # At least 5 bars apart
                    # Check if there's a lower price between the peaks
                    between_idx = range(peaks[-2][0] + 1, peaks[-1][0])
                    if any(recent_closes[i] < recent_closes[peaks[-2][0]] * 0.98 for i in between_idx):
                        return "double_top"

        # Head and shoulders pattern (check last 3 peaks)
        if len(peaks) >= 3:
            if peaks[-2][1] > peaks[-1][1] * 1.02 and peaks[-2][1] > peaks[-3][1] * 1.02:
                # Middle peak is highest
                if abs(peaks[-1][1] - peaks[-3][1]) / peaks[-3][1] < 0.05:
                    # First and third peaks are similar heights
                    return "head_shoulders"

        # Inverse head and shoulders (check last 3 troughs)
        if len(troughs) >= 3:
            if troughs[-2][1] < troughs[-1][1] * 0.98 and troughs[-2][1] < troughs[-3][1] * 0.98:
                # Middle trough is lowest
                if abs(troughs[-1][1] - troughs[-3][1]) / troughs[-3][1] < 0.05:
                    # First and third troughs are similar depths
                    return "inverse_head_shoulders"

        # Check for trend patterns
        if len(sma5) > 0 and len(sma20) > 0:
            # Adjust indices to match shortened arrays due to convolution
            sma5_recent = sma5[-5:]
            sma20_recent = sma20[-5:]

            # Bullish trend
            if all(sma5_recent[i] > sma20_recent[i] for i in range(len(sma5_recent))):
                return "bullish_trend"

            # Bearish trend
            if all(sma5_recent[i] < sma20_recent[i] for i in range(len(sma5_recent))):
                return "bearish_trend"

            # Crossover (bullish)
            if sma5[-1] > sma20[-1] and sma5[-2] <= sma20[-2]:
                return "bullish_crossover"

            # Crossover (bearish)
            if sma5[-1] < sma20[-1] and sma5[-2] >= sma20[-2]:
                return "bearish_crossover"

        # No clear pattern detected
        return "no_clear_pattern"

    except Exception as e:
        logger.error(f"Error detecting intraday pattern: {str(e)}")
        return "error_in_pattern_detection"

  def get_time_of_day_factor(self, current_hour: int, symbol: str) -> float:
    """
    Calculate a factor indicating how active/volatile trading typically is at the current hour

    Args:
        current_hour: Current hour of the day (0-23)
        symbol: Trading symbol for potential asset-specific adjustments

    Returns:
        Factor where 1.0 is average activity, >1 is higher activity, <1 is lower activity
    """
    try:
        # Define activity patterns for different market hours
        # These are generalized patterns that could be refined with historical data
        # Highest activity: Market opens, US lunch time, US market close
        high_activity_hours = [1, 2, 9, 10, 13, 14, 19, 20, 21]  # Peaks of activity
        medium_activity_hours = [3, 8, 11, 12, 15, 18, 22]  # Moderate activity
        low_activity_hours = [0, 4, 5, 6, 7, 16, 17, 23]  # Quieter periods

        # Special handling for specific symbols (can be expanded)
        if symbol.endswith("USDT"):
            # For USD-paired tokens, adjust for US market hours
            # Increase activity during US trading hours
            if 13 <= current_hour <= 20:  # Approximately US trading hours
                return 1.3

        # Return factor based on time of day
        if current_hour in high_activity_hours:
            return 1.5  # 50% more active than average
        elif current_hour in medium_activity_hours:
            return 1.0  # Average activity
        else:
            return 0.7  # 30% less active than average
    except Exception as e:
        logger.error(f"Error calculating time of day factor: {str(e)}")
        return 1.0  # Default to average activity

  def calculate_intraday_volatility(self, prices: List[float]) -> float:
    """
    Calculate a specialized volatility metric for intraday trading

    Args:
        prices: List of recent prices (preferably from short timeframes)

    Returns:
        Volatility metric as a float
    """
    try:
        if len(prices) < 5:
            return 0.01  # Default value for insufficient data

        # Convert to numpy array
        price_array = np.array(prices)

        # Calculate price changes as percentages
        pct_changes = np.diff(price_array) / price_array[:-1]

        # Calculate absolute percentage changes
        abs_changes = np.abs(pct_changes)

        # Calculate various volatility metrics
        std_dev = np.std(pct_changes)
        avg_abs_change = np.mean(abs_changes)
        max_change = np.max(abs_changes)

        # Calculate range-based volatility
        price_range = np.max(price_array) - np.min(price_array)
        range_volatility = price_range / np.mean(price_array)

        # Weight recent volatility more heavily
        recent_weight = 1.5
        if len(pct_changes) >= 10:
            recent_vol = np.std(pct_changes[-10:])
            weighted_vol = (std_dev + recent_vol * recent_weight) / (1 + recent_weight)
        else:
            weighted_vol = std_dev

        # Combine metrics for a comprehensive volatility measure
        # This formula weights different aspects of volatility
        combined_volatility = (
            weighted_vol * 0.5 +    # Standard deviation with recency bias
            avg_abs_change * 0.3 +  # Average movement
            max_change * 0.1 +      # Maximum movement
            range_volatility * 0.1  # Total range
        )

        return combined_volatility
    except Exception as e:
        logger.error(f"Error calculating intraday volatility: {str(e)}")
        return 0.01  # Default value

  def calculate_relative_volume(self, volumes: List[float]) -> float:
    """
    Calculate the relative volume compared to historical average

    Args:
        volumes: List of historical trading volumes

    Returns:
        Relative volume as a float (1.0 means average volume)
    """
    try:
        if len(volumes) < 10:
            return 1.0  # Default value for insufficient data

        # Convert to numpy array
        volume_array = np.array(volumes)

        # Calculate the historical average volume (excluding the most recent)
        historical_avg = np.mean(volume_array[:-1])

        # Get the most recent volume
        current_volume = volume_array[-1]

        # Calculate relative volume
        if historical_avg > 0:
            relative_vol = current_volume / historical_avg
        else:
            relative_vol = 1.0

        return relative_vol
    except Exception as e:
        logger.error(f"Error calculating relative volume: {str(e)}")
        return 1.0  # Default value

helpers = Helpers()
