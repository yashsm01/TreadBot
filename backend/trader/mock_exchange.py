import logging
from typing import Dict, Optional
import random
from datetime import datetime

logger = logging.getLogger(__name__)

class MockExchange:
    """Mock exchange for testing and simulation when real exchange is not available"""

    def __init__(self):
        self.prices = {
            "BTC/USDT": 50000.0,
            "ETH/USDT": 3000.0,
            "BNB/USDT": 400.0,
            "GUN/USDT": 200.0
        }
        self.balances = {
            "USDT": 10000.0,
            "BTC": 0.1,
            "ETH": 1.0,
            "BNB": 10.0,
            "GUN": 100.0
        }
        self.orders = {}
        self.order_id_counter = 0

    async def fetch_ticker(self, symbol: str) -> Dict:
        """Simulate fetching ticker data"""
        try:
            # Simulate price movement
            current_price = self.prices.get(symbol, 0.0)
            price_change = random.uniform(-0.1, 0.1)  # Random price change between -0.1% and 0.1%
            new_price = current_price * (1 + price_change)
            self.prices[symbol] = new_price

            return {
                "symbol": symbol,
                "last": new_price,
                "bid": new_price * 0.999,
                "ask": new_price * 1.001,
                "volume": random.uniform(100, 1000),
                "timestamp": datetime.now().timestamp() * 1000
            }
        except Exception as e:
            logger.error(f"Error in mock fetch_ticker: {str(e)}")
            raise

    async def fetch_balance(self) -> Dict:
        """Simulate fetching balance data"""
        try:
            return {
                currency: {
                    "free": amount,
                    "used": 0.0,
                    "total": amount
                }
                for currency, amount in self.balances.items()
            }
        except Exception as e:
            logger.error(f"Error in mock fetch_balance: {str(e)}")
            raise

    async def create_order(self, symbol: str, type: str, side: str, amount: float, price: Optional[float] = None) -> Dict:
        """Simulate order creation"""
        try:
            self.order_id_counter += 1
            order_id = str(self.order_id_counter)

            order = {
                "id": order_id,
                "symbol": symbol,
                "type": type,
                "side": side,
                "amount": amount,
                "price": price or self.prices.get(symbol, 0.0),
                "status": "open",
                "timestamp": datetime.now().timestamp() * 1000
            }

            self.orders[order_id] = order
            return order
        except Exception as e:
            logger.error(f"Error in mock create_order: {str(e)}")
            raise

    async def cancel_order(self, order_id: str, symbol: str) -> Dict:
        """Simulate order cancellation"""
        try:
            if order_id in self.orders:
                order = self.orders[order_id]
                order["status"] = "canceled"
                return order
            raise Exception(f"Order {order_id} not found")
        except Exception as e:
            logger.error(f"Error in mock cancel_order: {str(e)}")
            raise

    async def fetch_order(self, order_id: str, symbol: str) -> Dict:
        """Simulate fetching order status"""
        try:
            if order_id in self.orders:
                return self.orders[order_id]
            raise Exception(f"Order {order_id} not found")
        except Exception as e:
            logger.error(f"Error in mock fetch_order: {str(e)}")
            raise
