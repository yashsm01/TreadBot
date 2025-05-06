from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.core.logger import logger
from app.core.config import settings
from app.models.trade import Trade
from app.schemas.trade import TradeCreate
from app.crud.crud_trade import trade as trade_crud

class StraddleService:
    def __init__(self, db: Session):
        self.db = db

    async def create_straddle_trades(self, symbol: str, entry_price: float, quantity: float, breakout_pct: float) -> List[Trade]:
        """Create a pair of straddle trades (long and short) for a given symbol"""
        try:
            # Calculate take profit and stop loss levels
            tp_pct = settings.DEFAULT_TP_PCT
            sl_pct = settings.DEFAULT_SL_PCT

            # Create long trade
            long_trade = TradeCreate(
                symbol=symbol,
                side="BUY",
                entry_price=entry_price,
                quantity=quantity,
                take_profit=entry_price * (1 + tp_pct),
                stop_loss=entry_price * (1 - sl_pct),
                status="OPEN"
            )
            long_trade_db = await trade_crud.create(self.db, obj_in=long_trade)

            # Create short trade
            short_trade = TradeCreate(
                symbol=symbol,
                side="SELL",
                entry_price=entry_price,
                quantity=quantity,
                take_profit=entry_price * (1 - tp_pct),
                stop_loss=entry_price * (1 + sl_pct),
                status="OPEN"
            )
            short_trade_db = await trade_crud.create(self.db, obj_in=short_trade)

            logger.info(f"Created straddle trades for {symbol} at {entry_price}")
            return [long_trade_db, short_trade_db]

        except Exception as e:
            logger.error(f"Error creating straddle trades: {str(e)}")
            raise

    async def close_straddle_trades(self, symbol: str) -> List[Trade]:
        """Close all open straddle trades for a given symbol"""
        try:
            open_trades = await trade_crud.get_multi_by_symbol_and_status(
                self.db, symbol=symbol, status="OPEN"
            )
            closed_trades = []

            for trade in open_trades:
                trade.status = "CLOSED"
                trade.closed_at = datetime.utcnow()
                closed_trade = await trade_crud.update(self.db, db_obj=trade)
                closed_trades.append(closed_trade)

            logger.info(f"Closed {len(closed_trades)} straddle trades for {symbol}")
            return closed_trades

        except Exception as e:
            logger.error(f"Error closing straddle trades: {str(e)}")
            raise

straddle_service = StraddleService(None)  # Will be initialized with DB session later
