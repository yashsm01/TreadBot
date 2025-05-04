from binance.client import Client
from binance.exceptions import BinanceAPIException
from typing import Dict, Optional, List, Union
import logging
from ...core.logger import logger
from datetime import datetime

class BinanceHelper:
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Initialize Binance helper with optional API credentials
        For price data only, API keys are not required
        """
        self.client = Client(api_key, api_secret)

    async def get_price(self, symbol: str = "BTCUSDT") -> Dict[str, Union[str, float, int]]:
        """
        Get current price for a given trading pair
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT', 'ETHUSDT')
        Returns:
            Dictionary containing price information
        """
        try:
            # Convert symbol format if needed (BTC/USDT -> BTCUSDT)
            formatted_symbol = symbol.replace("/", "")
            ticker = self.client.get_symbol_ticker(symbol=formatted_symbol)
            current_time = int(datetime.utcnow().timestamp() * 1000)  # Convert to milliseconds

            return {
                "symbol": symbol,
                "price": float(ticker["price"]),
                "timestamp": current_time
            }
        except BinanceAPIException as e:
            logger.error(f"Error fetching price for {symbol}: {str(e)}")
            raise

    async def get_multiple_prices(self, symbols: List[str]) -> Dict[str, Dict[str, Union[float, int]]]:
        """
        Get current prices for multiple trading pairs
        Args:
            symbols: List of trading pair symbols (e.g., ['BTC/USDT', 'ETH/USDT'])
        Returns:
            Dictionary containing price information for all requested symbols
        """
        try:
            tickers = self.client.get_all_tickers()
            prices = {}
            current_time = int(datetime.utcnow().timestamp() * 1000)  # Convert to milliseconds

            # Convert symbols to Binance format
            formatted_symbols = {s.replace("/", ""): s for s in symbols}

            for ticker in tickers:
                original_symbol = formatted_symbols.get(ticker['symbol'])
                if original_symbol:
                    prices[original_symbol] = {
                        "price": float(ticker['price']),
                        "timestamp": current_time
                    }

            return prices
        except BinanceAPIException as e:
            logger.error(f"Error fetching prices: {str(e)}")
            raise

    async def get_24h_stats(self, symbol: str) -> Dict[str, Union[str, float]]:
        """
        Get 24-hour price statistics for a symbol
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
        Returns:
            Dictionary containing 24h statistics
        """
        try:
            formatted_symbol = symbol.replace("/", "")
            stats = self.client.get_ticker(symbol=formatted_symbol)
            current_time = int(datetime.utcnow().timestamp() * 1000)  # Convert to milliseconds

            return {
                "symbol": symbol,
                "high": float(stats["highPrice"]),
                "low": float(stats["lowPrice"]),
                "volume": float(stats["volume"]),
                "price_change": float(stats["priceChange"]),
                "price_change_percent": float(stats["priceChangePercent"]),
                "timestamp": current_time
            }
        except BinanceAPIException as e:
            logger.error(f"Error fetching 24h stats for {symbol}: {str(e)}")
            raise

# Create singleton instance
binance_helper = BinanceHelper()
