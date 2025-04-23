import ccxt
import logging
from typing import Dict, Optional
from dotenv import load_dotenv
import os
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

class ExchangeManager:
    def __init__(self):
        load_dotenv()
        self.exchange = None
        self.initialize_exchange()

    def initialize_exchange(self):
        try:
            self.exchange = ccxt.binance({
                'apiKey': os.getenv('BINANCE_API_KEY'),
                'secret': os.getenv('BINANCE_API_SECRET'),
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot'
                }
            })
            logger.info("Exchange initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing exchange: {str(e)}")
            raise

    async def get_balance(self, currency: str) -> float:
        try:
            balance = await self.exchange.fetch_balance()
            return float(balance.get(currency, {}).get('free', 0))
        except Exception as e:
            logger.error(f"Error fetching balance for {currency}: {str(e)}")
            raise

    async def get_ticker(self, symbol: str) -> Dict:
        try:
            return await self.exchange.fetch_ticker(symbol)
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {str(e)}")
            raise

    async def fetch_ticker(self, symbol: str) -> Dict:
        """
        Fetch current ticker data for a symbol

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')

        Returns:
            Dict containing ticker data
        """
        try:
            # For now, return mock data
            current_price = 50000.0  # Mock BTC price
            if symbol == "ETH/USDT":
                current_price = 3000.0
            elif symbol == "BNB/USDT":
                current_price = 400.0
            elif symbol == "GUN/USDT":
                current_price = 0.1

            return {
                'symbol': symbol,
                'last': current_price,
                'bid': current_price * 0.999,
                'ask': current_price * 1.001,
                'high': current_price * 1.02,
                'low': current_price * 0.98,
                'volume': 1000.0,
                'timestamp': datetime.now().timestamp() * 1000
            }
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {str(e)}")
            raise

    async def create_order(self, symbol: str, order_type: str, side: str, amount: float, price: Optional[float] = None) -> Dict:
        """
        Create a new order

        Args:
            symbol: Trading pair symbol
            order_type: Type of order (limit, market)
            side: Order side (buy, sell)
            amount: Order amount
            price: Order price (required for limit orders)

        Returns:
            Dict containing order information
        """
        try:
            # For now, return mock order data
            return {
                'id': str(uuid.uuid4()),
                'symbol': symbol,
                'type': order_type,
                'side': side,
                'amount': amount,
                'price': price,
                'status': 'closed',
                'timestamp': datetime.now().timestamp() * 1000
            }
        except Exception as e:
            logger.error(f"Error creating order: {str(e)}")
            raise

    async def fetch_order(self, order_id: str, symbol: str) -> Dict:
        """
        Fetch order information

        Args:
            order_id: Order ID
            symbol: Trading pair symbol

        Returns:
            Dict containing order information
        """
        try:
            # For now, return mock order data
            return {
                'id': order_id,
                'symbol': symbol,
                'type': 'limit',
                'side': 'buy',
                'amount': 0.1,
                'price': 50000.0,
                'status': 'closed',
                'timestamp': datetime.now().timestamp() * 1000
            }
        except Exception as e:
            logger.error(f"Error fetching order: {str(e)}")
            raise

    async def cancel_order(self, order_id: str, symbol: str) -> Dict:
        """
        Cancel an existing order

        Args:
            order_id: Order ID
            symbol: Trading pair symbol

        Returns:
            Dict containing cancellation information
        """
        try:
            # For now, return mock cancellation data
            return {
                'id': order_id,
                'symbol': symbol,
                'status': 'canceled',
                'timestamp': datetime.now().timestamp() * 1000
            }
        except Exception as e:
            logger.error(f"Error canceling order: {str(e)}")
            raise

    async def get_order_status(self, order_id: str, symbol: str) -> Dict:
        try:
            return await self.exchange.fetch_order(order_id, symbol)
        except Exception as e:
            logger.error(f"Error fetching order status for {order_id}: {str(e)}")
            raise

    def get_exchange(self) -> ccxt.Exchange:
        if not self.exchange:
            self.initialize_exchange()
        return self.exchange
