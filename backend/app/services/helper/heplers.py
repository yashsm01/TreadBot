import pytz
from datetime import datetime
import uuid
import numpy as np
from typing import List, Tuple
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

  def calculate_dynamic_profit_threshold(self, price_history: List[float], symbol: str) -> Tuple[float, float, float]:
    """
    Calculate dynamic profit thresholds based on price volatility

    Args:
        price_history: List of historical prices
        symbol: Trading symbol for logging

    Returns:
        Tuple of (small, medium, large) threshold values
    """
    try:
        if not price_history or len(price_history) < 2:
            logger.warning(f"Insufficient price data for {symbol}. Using default thresholds.")
            return 0.01, 0.025, 0.04

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
        threshold_small = max(0.008, min_intraday_move, volatility_ratio * 0.6)  # Minimum 0.8%
        threshold_medium = max(0.018, min_intraday_move * 2, volatility_ratio * 1.4)  # Minimum 1.8%
        threshold_large = max(0.03, min_intraday_move * 3, volatility_ratio * 2.2)  # Minimum 3%

        logger.info(f"Dynamic thresholds for {symbol}: small={threshold_small:.4f}, medium={threshold_medium:.4f}, large={threshold_large:.4f}, volatility={volatility_ratio:.4f}")
        return threshold_small, threshold_medium, threshold_large
    except Exception as e:
        logger.error(f"Error calculating dynamic profit thresholds: {str(e)}")
        # Fallback to default values
        return 0.01, 0.025, 0.04

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

helpers = Helpers()
