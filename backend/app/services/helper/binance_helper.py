from binance.client import Client
from binance.exceptions import BinanceAPIException
from typing import Dict, Optional, List, Union
import logging
from app.core.logger import logger
from datetime import datetime
import numpy as np
from app.core.config import settings
import time

class BinanceHelper:
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Initialize Binance helper with optional API credentials
        For price data only, API keys are not required
        """
        self.client = Client(api_key, api_secret)

    # Get current price for a given trading pair
    async def get_price(self, symbol: str = "BTCUSDT") -> Dict[str, Union[str, float, int]]:
        """
        Get current price for a given trading pair
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT', 'ETHUSDT')
        Returns:
            Dictionary containing price information
        """
        try:
            if self.is_stablecoin(symbol):
                return {"symbol": symbol, "price": 1.0, "time": int(time.time() * 1000)}
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

    async def get_enhanced_price_data(self, symbol: str) -> Dict[str, Union[str, float, Dict]]:
        """
        Get enhanced price data including price, 24h change, volume, and additional metrics

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT', 'ETHUSDT')

        Returns:
            Dictionary containing comprehensive price data
        """
        try:
            # Handle stablecoins with fixed price
            if self.is_stablecoin(symbol):
                return {
                    "symbol": symbol,
                    "price": 1.0,
                    "price_change_24h": 0.0,
                    "price_change_percentage_24h": 0.0,
                    "volume_24h": 0.0,
                    "high_24h": 1.0,
                    "low_24h": 1.0,
                    "market_cap": 0.0,  # Not available for stablecoins
                    "is_stablecoin": True,
                    "timestamp": int(time.time() * 1000)
                }

            # For crypto assets, get comprehensive data
            formatted_symbol = symbol.replace("/", "")

            # Get ticker data (includes price and 24h stats)
            ticker = self.client.get_ticker(symbol=formatted_symbol)

            # Get 5-minute data for short-term momentum
            try:
                short_term_data = await self.get_5m_stats(symbol)
                short_term_change = short_term_data.get("price_change_percent", 0.0)
            except Exception as st_error:
                logger.warning(f"Could not fetch short-term data for {symbol}: {str(st_error)}")
                short_term_change = 0.0

            # Estimate market cap if volume is available (rough approximation)
            # Real market cap would require circulating supply data
            volume_24h = float(ticker.get("volume", 0.0))
            current_price = float(ticker.get("lastPrice", 0.0))

            # Calculate volatility from 24h high/low
            high_24h = float(ticker.get("highPrice", current_price))
            low_24h = float(ticker.get("lowPrice", current_price))
            volatility_24h = (high_24h - low_24h) / current_price if current_price > 0 else 0.0

            # Return comprehensive data
            return {
                "symbol": symbol,
                "price": current_price,
                "bid_price": float(ticker.get("bidPrice", 0.0)),
                "ask_price": float(ticker.get("askPrice", 0.0)),
                "price_change_24h": float(ticker.get("priceChange", 0.0)),
                "price_change_percentage_24h": float(ticker.get("priceChangePercent", 0.0)),
                "volume_24h": volume_24h,
                "quote_volume": float(ticker.get("quoteVolume", 0.0)),
                "high_24h": high_24h,
                "low_24h": low_24h,
                "open_24h": float(ticker.get("openPrice", 0.0)),
                "number_of_trades": int(ticker.get("count", 0)),
                "short_term_change_percent": short_term_change,
                "volatility_24h": volatility_24h,
                "is_stablecoin": False,
                "timestamp": int(time.time() * 1000)
            }
        except BinanceAPIException as e:
            logger.error(f"Error fetching enhanced price data for {symbol}: {str(e)}")
            # Return basic price data as fallback
            try:
                basic_price = await self.get_price(symbol)
                return {
                    "symbol": symbol,
                    "price": basic_price.get("price", 0.0),
                    "price_change_percentage_24h": 0.0,
                    "volume_24h": 0.0,
                    "is_fallback": True,
                    "error": str(e),
                    "timestamp": int(time.time() * 1000)
                }
            except Exception as fallback_error:
                logger.error(f"Fallback error for {symbol}: {str(fallback_error)}")
                return {
                    "symbol": symbol,
                    "price": 0.0,
                    "price_change_percentage_24h": 0.0,
                    "volume_24h": 0.0,
                    "error": f"{str(e)} (fallback failed: {str(fallback_error)})",
                    "timestamp": int(time.time() * 1000)
                }

    # Get current prices for multiple trading pairs
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

    async def get_multiple_enhanced_prices(self, symbols: List[str]) -> Dict[str, Dict[str, Union[float, Dict]]]:
        """
        Get enhanced price data for multiple trading pairs in a single call

        Args:
            symbols: List of trading pair symbols (e.g., ['BTCUSDT', 'ETHUSDT'])

        Returns:
            Dictionary mapping symbols to their enhanced price data
        """
        try:
            # Get all tickers in one API call
            tickers = self.client.get_ticker()
            ticker_map = {t['symbol']: t for t in tickers}

            # Prepare results
            results = {}
            current_time = int(time.time() * 1000)

            for symbol in symbols:
                try:
                    # Handle stablecoins
                    if self.is_stablecoin(symbol):
                        results[symbol] = {
                            "symbol": symbol,
                            "price": 1.0,
                            "price_change_24h": 0.0,
                            "price_change_percentage_24h": 0.0,
                            "volume_24h": 0.0,
                            "high_24h": 1.0,
                            "low_24h": 1.0,
                            "is_stablecoin": True,
                            "timestamp": current_time
                        }
                        continue

                    # For regular crypto assets
                    formatted_symbol = symbol.replace("/", "")
                    ticker = ticker_map.get(formatted_symbol)

                    if not ticker:
                        logger.warning(f"No ticker data found for {symbol}")
                        results[symbol] = {
                            "symbol": symbol,
                            "price": 0.0,
                            "error": "No ticker data found",
                            "timestamp": current_time
                        }
                        continue

                    current_price = float(ticker.get("lastPrice", 0.0))
                    high_24h = float(ticker.get("highPrice", current_price))
                    low_24h = float(ticker.get("lowPrice", current_price))
                    volatility_24h = (high_24h - low_24h) / current_price if current_price > 0 else 0.0

                    results[symbol] = {
                        "symbol": symbol,
                        "price": current_price,
                        "price_change_24h": float(ticker.get("priceChange", 0.0)),
                        "price_change_percentage_24h": float(ticker.get("priceChangePercent", 0.0)),
                        "volume_24h": float(ticker.get("volume", 0.0)),
                        "high_24h": high_24h,
                        "low_24h": low_24h,
                        "volatility_24h": volatility_24h,
                        "is_stablecoin": False,
                        "timestamp": current_time
                    }
                except Exception as symbol_error:
                    logger.error(f"Error processing {symbol}: {str(symbol_error)}")
                    results[symbol] = {
                        "symbol": symbol,
                        "price": 0.0,
                        "error": str(symbol_error),
                        "timestamp": current_time
                    }

            return results
        except BinanceAPIException as e:
            logger.error(f"Error fetching multiple enhanced prices: {str(e)}")
            return {symbol: {"symbol": symbol, "price": 0.0, "error": str(e), "timestamp": int(time.time() * 1000)}
                    for symbol in symbols}

    # Get 24-hour price statistics for a symbol
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

    # Get 5-minute candlestick statistics for a symbol
    async def get_5m_stats(self, symbol: str) -> Dict[str, Union[str, float, int]]:
        """
        Get 5-minute candlestick statistics for a symbol
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
        Returns:
            Dictionary containing 5m candlestick statistics
        """
        try:
            formatted_symbol = symbol.replace("/", "")
            # Get the most recent 5m candlestick
            klines = self.client.get_klines(
                symbol=formatted_symbol,
                interval=Client.KLINE_INTERVAL_5MINUTE,
                limit=1
            )

            if not klines:
                raise BinanceAPIException("No kline data available")

              # Unpack the kline data
            # [0]Open time, [1]Open, [2]High, [3]Low, [4]Close, [5]Volume, [6]Close time
            kline = klines[0]

            return {
                "symbol": symbol,
                "open_time": kline[0],
                "close_time": kline[6],
                "open": float(kline[1]),
                "high": float(kline[2]),
                "low": float(kline[3]),
                "close": float(kline[4]),
                "volume": float(kline[5]),
                "price_change": float(kline[4]) - float(kline[1]),  # close - open
                "price_change_percent": ((float(kline[4]) - float(kline[1])) / float(kline[1])) * 100,
                "number_of_trades": int(kline[8]),
                "taker_buy_volume": float(kline[9]),
                "taker_buy_quote_volume": float(kline[10]),
                "timestamp": int(datetime.utcnow().timestamp() * 1000)
            }
        except BinanceAPIException as e:
            logger.error(f"Error fetching 5m stats for {symbol}: {str(e)}")
            raise
        except (IndexError, ValueError) as e:
            logger.error(f"Error processing 5m kline data for {symbol}: {str(e)}")
            raise BinanceAPIException(f"Error processing kline data: {str(e)}")

    # Get historical 5-minute price data with variations
    async def get_5m_price_history(self, symbol: str, intervals: int = 5) -> Dict[str, Union[Dict, List]]:
        """
        Get historical 5-minute price data with variations
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            intervals: Number of 5-minute intervals to fetch (default: 5)
        Returns:
            Dictionary containing historical prices, variations, and statistics
        """
        try:
            formatted_symbol = symbol.replace("/", "")
            # Get the klines data for the last 5 intervals
            klines = self.client.get_klines(
                symbol=formatted_symbol,
                interval=Client.KLINE_INTERVAL_5MINUTE,
                limit=intervals
            )

            if not klines or len(klines) < intervals:
                raise BinanceAPIException(f"Insufficient kline data. Required: {intervals}, Got: {len(klines) if klines else 0}")

            # Process each kline into a price entry
            price_history = []
            close_prices = []

            for kline in klines:
                close_price = float(kline[4])  # Close price
                close_prices.append(close_price)

                price_entry = {
                    "timestamp": kline[0],  # Open time
                    "open": float(kline[1]),
                    "high": float(kline[2]),
                    "low": float(kline[3]),
                    "close": close_price,
                    "volume": float(kline[5]),
                    "number_of_trades": int(kline[8])
                }
                price_history.append(price_entry)

            # Calculate variations and differences
            close_prices = np.array(close_prices)
            price_changes = np.diff(close_prices)
            price_changes_percent = (price_changes / close_prices[:-1]) * 100

            # Calculate statistics
            stats = {
                "mean_price": float(np.mean(close_prices)),
                "std_dev": float(np.std(close_prices)),
                "max_price": float(np.max(close_prices)),
                "min_price": float(np.min(close_prices)),
                "total_change": float(close_prices[-1] - close_prices[0]),
                "total_change_percent": float((close_prices[-1] - close_prices[0]) / close_prices[0] * 100),
                "volatility": float(np.std(price_changes_percent))  # Standard deviation of percent changes
            }

            # Add price changes to history
            for i in range(len(price_history)-1):
                price_history[i+1].update({
                    "price_change": float(price_changes[i]),
                    "price_change_percent": float(price_changes_percent[i])
                })

            # First entry doesn't have changes (it's the oldest)
            price_history[0].update({
                "price_change": 0.0,
                "price_change_percent": 0.0
            })

            return {
                "data": {
                    "symbol": symbol,
                    "interval": "5m",
                    "history": price_history,
                    "statistics": stats,
                    "timestamp": int(datetime.utcnow().timestamp() * 1000)
                }
            }

        except BinanceAPIException as e:
            logger.error(f"Error fetching 5m price history for {symbol}: {str(e)}")
            raise
        except (IndexError, ValueError) as e:
            logger.error(f"Error processing 5m price history for {symbol}: {str(e)}")
            raise BinanceAPIException(f"Error processing price history: {str(e)}")

    #get Dynamic interval price history
    async def get_dynamic_price_history(self, symbol: str, interval: str = "5m", intervals: int = 5) -> Dict[str, Union[Dict, List]]:
        """
        Get historical price data for a given symbol and interval
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            interval: Interval to fetch (e.g., '5m', '15m', '30m', '1h', '4h', '1d')
            intervals: Number of intervals to fetch (default: 5)
        Returns:
            Dictionary containing historical prices, variations, and statistics
        """
        try:
            formatted_symbol = symbol.replace("/", "")
            # Get the klines data for the last 5 intervals
            klines = self.client.get_klines(
                symbol=formatted_symbol,
                interval=Client.KLINE_INTERVAL_15MINUTE,
                limit=intervals
            )

            if not klines or len(klines) < 10:
                raise BinanceAPIException(f"Insufficient kline data. Required: {intervals}, Got: {len(klines) if klines else 0}")

            # Process each kline into a price entry
            price_history = []
            close_prices = []

            for kline in klines:
                close_price = float(kline[4])  # Close price
                close_prices.append(close_price)

                price_entry = {
                    "timestamp": kline[0],  # Open time
                    "open": float(kline[1]),
                    "high": float(kline[2]),
                    "low": float(kline[3]),
                    "close": close_price,
                    "volume": float(kline[5]),
                    "number_of_trades": int(kline[8])
                }
                price_history.append(price_entry)

                # Calculate variations and differences
            close_prices = np.array(close_prices)
            price_changes = np.diff(close_prices)
            price_changes_percent = (price_changes / close_prices[:-1]) * 100

            # Calculate statistics
            stats = {
                "mean_price": float(np.mean(close_prices)),
                "std_dev": float(np.std(close_prices)),
                "max_price": float(np.max(close_prices)),
                "min_price": float(np.min(close_prices)),
                "total_change": float(close_prices[-1] - close_prices[0]),
                "total_change_percent": float((close_prices[-1] - close_prices[0]) / close_prices[0] * 100),
                "volatility": float(np.std(price_changes_percent))  # Standard deviation of percent changes
            }

            # Add price changes to history
            for i in range(len(price_history)-1):
                price_history[i+1].update({
                    "price_change": float(price_changes[i]),
                    "price_change_percent": float(price_changes_percent[i])
                })

            # First entry doesn't have changes (it's the oldest)
            price_history[0].update({
                "price_change": 0.0,
                "price_change_percent": 0.0
            })

            return {
                "data": {
                    "symbol": symbol,
                    "interval": "15m",
                    "history": price_history,
                    "statistics": stats,
                    "timestamp": int(datetime.utcnow().timestamp() * 1000)
                }
            }
        except BinanceAPIException as e:
            logger.error(f"Error fetching 15m price history for {symbol}: {str(e)}")
            raise
        except (IndexError, ValueError) as e:
            logger.error(f"Error processing 15m price history for {symbol}: {str(e)}")
            raise BinanceAPIException(f"Error processing price history: {str(e)}")

    #get the best stable coin to buy from the binance array from live market
    async def get_best_stable_coin(self) -> Dict[str, Union[str, Dict, List]]:
        """
        Get the best stablecoin by analyzing market data and return detailed information

        Returns:
            Dictionary containing the best stablecoin symbol and detailed information for all analyzed stablecoins
        """
        try:
            # Common stablecoins on Binance
            stablecoins = settings.STABLE_COINS

            # Get 24hr stats for BTC paired with each stablecoin
            stats = {}
            for stable in stablecoins:
                try:
                    pair = f"BTC{stable}"
                    # Get statistics for this pair
                    ticker = await self.get_24h_stats(pair)

                    # Calculate metrics (volume and liquidity are good indicators)
                    volume = ticker["volume"]

                    stats[stable] = {
                        "symbol": stable,
                        "pair": pair,
                        "volume": volume,
                        "price_change_percent": ticker["price_change_percent"],
                        "high": ticker["high"],
                        "low": ticker["low"],
                        "price_change": ticker["price_change"],
                        "timestamp": ticker["timestamp"]
                    }

                    logger.info(f"Analyzed stablecoin {stable}: volume=${volume:,.2f}")
                except Exception as e:
                    # This pair might not exist, skip it
                    logger.warning(f"Pair BTC{stable} not available: {str(e)}")
                    continue

            if not stats:
                # Default to USDT if no data available
                logger.warning("No stablecoin data available, defaulting to USDT")
                return {
                    "best_stable": "USDT",
                    "available_stables": ["USDT"],
                    "reason": "No stablecoin data available",
                    "all_stables": {}
                }

            # Rank stablecoins by volume (higher is better)
            best_stable = max(stats.items(), key=lambda x: x[1]["volume"])[0]

            # List of available stables (all that we have stats for)
            available_stables = list(stats.keys())

            logger.info(f"Selected {best_stable} as the best stablecoin based on volume")

            return {
                "best_stable": best_stable,
                "available_stables": available_stables,
                "reason": "Highest trading volume",
                "best_metrics": stats[best_stable],
                "all_stables": stats,
                "timestamp": int(datetime.utcnow().timestamp() * 1000)
            }

        except Exception as e:
            logger.error(f"Error determining best stablecoin: {str(e)}")
            # Default to USDT in case of errors
            return {
                "best_stable": "USDT",
                "available_stables": ["USDT"],
                "reason": f"Error: {str(e)}",
                "all_stables": {},
                "timestamp": int(datetime.utcnow().timestamp() * 1000)
            }

    async def get_stablecoin_balances(self, portfolio_data: Dict) -> Dict[str, Dict]:
        """
        Analyze portfolio data to find stablecoin balances

        Args:
            portfolio_data: Dictionary of portfolio data containing assets

        Returns:
            Dictionary mapping stablecoin symbols to their balance information
        """
        stablecoin_balances = {}

        try:
            # All supported stablecoins
            all_stablecoins = settings.STABLE_COINS

            # Extract stablecoin balances from portfolio
            for symbol, asset_data in portfolio_data.items():
                if symbol in all_stablecoins or asset_data.get("asset_type") == "STABLE":
                    stablecoin_balances[symbol] = {
                        "symbol": symbol,
                        "quantity": asset_data.get("quantity", 0.0),
                        "value": asset_data.get("value", 0.0),
                        "timestamp": int(time.time() * 1000)
                    }

            # Return data sorted by value (largest first)
            sorted_balances = {k: v for k, v in sorted(
                stablecoin_balances.items(),
                key=lambda item: item[1].get("value", 0.0),
                reverse=True
            )}

            return sorted_balances

        except Exception as e:
            logger.error(f"Error getting stablecoin balances: {str(e)}")
            return stablecoin_balances

    # Helper function to format timestamp
    def _format_timestamp(self, timestamp_ms: int) -> str:
        """Convert millisecond timestamp to readable format"""
        dt = datetime.fromtimestamp(timestamp_ms / 1000)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    # Helper function to check if a symbol is a stablecoin
    def is_stablecoin(self, symbol: str) -> bool:
        """
        Check if a symbol is a stablecoin
        Args:
            symbol: Symbol to check
        Returns:
            True if the symbol is a stablecoin, False otherwise
        """
        common_stablecoins = ["USDT", "USDC", "BUSD", "DAI", "TUSD", "USDP", "USDD"]
        if symbol in common_stablecoins:
            return True
        return False

# Create singleton instance
binance_helper = BinanceHelper()
