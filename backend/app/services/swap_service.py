from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from app.core.logger import logger
from app.core.config import settings
from app.crud.crud_trade import trade as trade_crud
from app.crud.crud_portfolio import portfolio as portfolio_crud
from app.services.helper.heplers import helpers
from app.services.helper.binance_helper import binance_helper


class SwapService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def swap_buy(self, symbol: str, quantity: float, current_price: float) -> None:
        """Swap buy a position"""
        try:
            # Get the current price of the symbol
            crypto_details = await binance_helper.get_price(symbol)
            current_price = crypto_details["price"]

            #get most stable coin from binance array axcept the symbol

            #get the best stable coin to buy
            best_stable_coin = binance_helper.get_best_stable_coin(symbol)




        except Exception as e:
            logger.error(f"Error swapping buy: {e}")
            raise e from e



