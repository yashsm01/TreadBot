from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio
from app.services.helper.binance_helper import binance_helper
from app.core.logger import logger
from app.core.config import settings
import random

class LiveService:
    def __init__(self):
        self.binance = binance_helper
        # Popular trading pairs to fetch data for
        self.default_symbols = [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT",
            "DOTUSDT", "LINKUSDT", "MATICUSDT", "AVAXUSDT",
            "DOGEUSDT", "BNBUSDT", "XRPUSDT", "LTCUSDT"
        ]
        # Icon mapping for tokens
        self.token_icons = {
            "BTC": "₿",
            "ETH": "Ξ",
            "SOL": "◎",
            "ADA": "₳",
            "DOT": "●",
            "LINK": "🔗",
            "MATIC": "▲",
            "AVAX": "🔺",
            "DOGE": "🐕",
            "BNB": "🟡",
            "XRP": "💧",
            "LTC": "Ł"
        }

    async def get_live_tokens(self, symbols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get live token data formatted similar to mock tokens

        Args:
            symbols: List of token symbols to fetch (optional)

        Returns:
            List of token data dictionaries
        """
        try:
            # Use provided symbols or default ones
            target_symbols = symbols if symbols else self.default_symbols

            # Fetch enhanced price data for all symbols
            price_data = await self.binance.get_multiple_enhanced_prices(target_symbols)

            tokens = []
            for symbol in target_symbols:
                try:
                    data = price_data.get(symbol, {})
                    if not data or data.get('error'):
                        logger.warning(f"No data available for {symbol}")
                        continue

                    # Extract base symbol (e.g., BTC from BTCUSDT)
                    base_symbol = symbol.replace("USDT", "").replace("USDC", "").replace("BUSD", "")

                    # Format token data similar to mock structure
                    token = {
                        "id": base_symbol.lower(),
                        "symbol": base_symbol,
                        "name": self._get_token_name(base_symbol),
                        "price": round(data.get("price", 0.0), 6),
                        "change24h": round(data.get("price_change_percentage_24h", 0.0), 2),
                        "volume": int(data.get("volume_24h", 0.0)),
                        "marketCap": self._estimate_market_cap(data.get("price", 0.0), data.get("volume_24h", 0.0)),
                        "icon": self.token_icons.get(base_symbol, "🪙"),
                        "high24h": round(data.get("high_24h", 0.0), 6),
                        "low24h": round(data.get("low_24h", 0.0), 6),
                        "volatility": round(data.get("volatility_24h", 0.0), 4),
                        "timestamp": data.get("timestamp", int(datetime.now().timestamp() * 1000))
                    }
                    tokens.append(token)

                except Exception as e:
                    logger.error(f"Error processing token {symbol}: {str(e)}")
                    continue

            # Sort by market cap (estimated) descending
            tokens.sort(key=lambda x: x.get("marketCap", 0), reverse=True)

            return tokens

        except Exception as e:
            logger.error(f"Error fetching live tokens: {str(e)}")
            return []

    async def get_live_signals(self, symbols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Generate trading signals based on real market data

        Args:
            symbols: List of token symbols to analyze (optional)

        Returns:
            List of trading signal dictionaries
        """
        try:
            # Use provided symbols or default ones
            target_symbols = symbols if symbols else self.default_symbols[:3]  # Limit to 3 for signals

            signals = []

            for symbol in target_symbols:
                try:
                    # Get 5-minute price history for signal analysis
                    history_data = await self.binance.get_5m_price_history(symbol, intervals=10)

                    if not history_data or not history_data.get("data"):
                        continue

                    data = history_data["data"]
                    history = data.get("history", [])
                    stats = data.get("statistics", {})

                    if len(history) < 5:
                        continue

                    # Extract base symbol
                    base_symbol = symbol.replace("USDT", "").replace("USDC", "").replace("BUSD", "")

                    # Simple signal generation logic
                    signal = self._generate_signal(history, stats, base_symbol)

                    if signal:
                        signals.append(signal)

                except Exception as e:
                    logger.error(f"Error generating signal for {symbol}: {str(e)}")
                    continue

            return signals

        except Exception as e:
            logger.error(f"Error generating live signals: {str(e)}")
            return []

    async def get_token_details(self, symbol: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific token

        Args:
            symbol: Token symbol (e.g., 'BTCUSDT')

        Returns:
            Detailed token information dictionary
        """
        try:
            # Ensure symbol is in correct format
            if not symbol.endswith(("USDT", "USDC", "BUSD")):
                symbol = f"{symbol}USDT"

            # Get enhanced price data
            price_data = await self.binance.get_enhanced_price_data(symbol)

            if price_data.get('error'):
                return {"error": f"Failed to fetch data for {symbol}"}

            # Get 5-minute history
            history_data = await self.binance.get_5m_price_history(symbol, intervals=20)

            base_symbol = symbol.replace("USDT", "").replace("USDC", "").replace("BUSD", "")

            return {
                "id": base_symbol.lower(),
                "symbol": base_symbol,
                "name": self._get_token_name(base_symbol),
                "price": round(price_data.get("price", 0.0), 6),
                "change24h": round(price_data.get("price_change_percentage_24h", 0.0), 2),
                "volume": int(price_data.get("volume_24h", 0.0)),
                "marketCap": self._estimate_market_cap(price_data.get("price", 0.0), price_data.get("volume_24h", 0.0)),
                "icon": self.token_icons.get(base_symbol, "🪙"),
                "high24h": round(price_data.get("high_24h", 0.0), 6),
                "low24h": round(price_data.get("low_24h", 0.0), 6),
                "volatility": round(price_data.get("volatility_24h", 0.0), 4),
                "bidPrice": round(price_data.get("bid_price", 0.0), 6),
                "askPrice": round(price_data.get("ask_price", 0.0), 6),
                "shortTermChange": round(price_data.get("short_term_change_percent", 0.0), 2),
                "history": history_data.get("data", {}) if history_data else {},
                "timestamp": price_data.get("timestamp", int(datetime.now().timestamp() * 1000))
            }

        except Exception as e:
            logger.error(f"Error fetching token details for {symbol}: {str(e)}")
            return {"error": str(e)}

    def _get_token_name(self, symbol: str) -> str:
        """Get full token name from symbol"""
        token_names = {
            "BTC": "Bitcoin",
            "ETH": "Ethereum",
            "SOL": "Solana",
            "ADA": "Cardano",
            "DOT": "Polkadot",
            "LINK": "Chainlink",
            "MATIC": "Polygon",
            "AVAX": "Avalanche",
            "DOGE": "Dogecoin",
            "BNB": "BNB",
            "XRP": "XRP",
            "LTC": "Litecoin"
        }
        return token_names.get(symbol, symbol)

    def _estimate_market_cap(self, price: float, volume: float) -> int:
        """Estimate market cap based on price and volume (rough approximation)"""
        try:
            # This is a rough estimation - real market cap needs circulating supply
            # Using volume as a proxy for market activity
            if price > 0 and volume > 0:
                # Rough estimation based on typical volume/market cap ratios
                estimated_cap = volume * price * 100  # Very rough multiplier
                return int(estimated_cap)
            return 0
        except:
            return 0

    def _generate_signal(self, history: List[Dict], stats: Dict, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Generate a trading signal based on price history and statistics

        Args:
            history: Price history data
            stats: Statistical data
            symbol: Token symbol

        Returns:
            Trading signal dictionary or None
        """
        try:
            if len(history) < 5:
                return None

            current_price = history[-1]["close"]
            previous_prices = [h["close"] for h in history[-5:]]

            # Calculate simple moving average
            sma = sum(previous_prices) / len(previous_prices)

            # Calculate price momentum
            price_momentum = (current_price - previous_prices[0]) / previous_prices[0] * 100

            # Determine signal type based on momentum and volatility
            volatility = stats.get("volatility", 0)

            if price_momentum > 2 and volatility < 5:  # Strong upward momentum, low volatility
                signal_type = "LONG"
                entry = current_price
                stop_loss = current_price * 0.98  # 2% stop loss
                take_profit = current_price * 1.05  # 5% take profit
                confidence = min(85, 60 + abs(price_momentum))
            elif price_momentum < -2 and volatility < 5:  # Strong downward momentum, low volatility
                signal_type = "SHORT"
                entry = current_price
                stop_loss = current_price * 1.02  # 2% stop loss
                take_profit = current_price * 0.95  # 5% take profit
                confidence = min(85, 60 + abs(price_momentum))
            else:
                # No clear signal
                return None

            # Generate signal ID
            signal_id = f"signal-{symbol.lower()}-{int(datetime.now().timestamp())}"

            return {
                "id": signal_id,
                "tokenId": symbol.lower(),
                "type": signal_type,
                "entry": round(entry, 6),
                "stopLoss": round(stop_loss, 6),
                "takeProfit": round(take_profit, 6),
                "confidence": int(confidence),
                "timestamp": datetime.now(),
                "status": "ACTIVE",
                "momentum": round(price_momentum, 2),
                "volatility": round(volatility, 2)
            }

        except Exception as e:
            logger.error(f"Error generating signal for {symbol}: {str(e)}")
            return None

# Create singleton instance
live_service = LiveService()
