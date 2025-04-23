import ccxt
import logging
from datetime import datetime
from typing import Dict, Optional
from ..db.models import Trade, TradeStatus, TradeType

logger = logging.getLogger(__name__)

class StraddleStrategy:
    def __init__(self, exchange: ccxt.Exchange, config: Dict):
        self.exchange = exchange
        self.config = config
        self.active_trades: Dict[str, Trade] = {}

    async def execute_strategy(self, symbol: str):
        try:
            # Fetch current market price
            ticker = await self.exchange.fetch_ticker(symbol)
            current_price = ticker['last']

            # Calculate order prices
            breakout_pct = self.config['breakout_pct']
            buy_price = current_price * (1 + breakout_pct / 100)
            sell_price = current_price * (1 - breakout_pct / 100)

            # Place orders
            buy_order = await self.place_order(symbol, 'buy', buy_price)
            sell_order = await self.place_order(symbol, 'sell', sell_price)

            # Create trade record
            trade = Trade(
                coin=symbol,
                entry_price=current_price,
                quantity=self.config['quantity'],
                type=TradeType.REAL if not self.config.get('paper_trading') else TradeType.PAPER
            )

            # Store active trade
            self.active_trades[symbol] = {
                'trade': trade,
                'buy_order': buy_order,
                'sell_order': sell_order
            }

            return trade

        except Exception as e:
            logger.error(f"Error executing strategy for {symbol}: {str(e)}")
            raise

    async def place_order(self, symbol: str, side: str, price: float):
        try:
            order = await self.exchange.create_order(
                symbol=symbol,
                type='limit',
                side=side,
                amount=self.config['quantity'],
                price=price
            )
            return order
        except Exception as e:
            logger.error(f"Error placing {side} order for {symbol}: {str(e)}")
            raise

    async def handle_order_fill(self, symbol: str, order_id: str):
        try:
            trade_info = self.active_trades.get(symbol)
            if not trade_info:
                return

            # Cancel the other order
            filled_order = trade_info['buy_order'] if order_id == trade_info['sell_order']['id'] else trade_info['sell_order']
            other_order = trade_info['sell_order'] if order_id == trade_info['buy_order']['id'] else trade_info['buy_order']

            await self.exchange.cancel_order(other_order['id'], symbol)

            # Update trade status
            trade = trade_info['trade']
            trade.status = TradeStatus.OPEN
            trade.entry_price = filled_order['price']

            # Set up take profit and stop loss
            tp_price = trade.entry_price * (1 + self.config['tp_pct'] / 100)
            sl_price = trade.entry_price * (1 - self.config['sl_pct'] / 100)

            # Place TP and SL orders
            await self.place_order(symbol, 'sell', tp_price)  # Take profit
            await self.place_order(symbol, 'sell', sl_price)  # Stop loss

        except Exception as e:
            logger.error(f"Error handling order fill for {symbol}: {str(e)}")
            raise

    async def close_position(self, symbol: str, price: float, is_tp: bool):
        try:
            trade_info = self.active_trades.get(symbol)
            if not trade_info:
                return

            trade = trade_info['trade']
            trade.exit_price = price
            trade.profit_pct = ((price - trade.entry_price) / trade.entry_price) * 100
            trade.status = TradeStatus.CLOSED

            # Remove from active trades
            del self.active_trades[symbol]

            return trade

        except Exception as e:
            logger.error(f"Error closing position for {symbol}: {str(e)}")
            raise
