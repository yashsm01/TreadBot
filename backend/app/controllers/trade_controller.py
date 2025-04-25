from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.services.trade_service import trade_service
from app.services.telegram_service import telegram_service
from app.schemas import trade as trade_schemas
from datetime import datetime

class TradeController:
    @staticmethod
    async def create_trade(db: Session, trade_data: trade_schemas.TradeCreate) -> trade_schemas.Trade:
        """Create a new trade and send notification"""
        try:
            trade = await trade_service.create_trade(db, trade_data)

            # Send Telegram notification
            await telegram_service.notify_trade_opened(
                symbol=trade.symbol,
                side=trade.side,
                quantity=trade.quantity,
                entry_price=trade.entry_price,
                strategy="TIME_BASED_STRADDLE"
            )

            return trade
        except Exception as e:
            await telegram_service.notify_error(f"Failed to create trade: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    async def close_trade(
        db: Session, trade_id: int, exit_price: float
    ) -> trade_schemas.Trade:
        """Close a trade and send notification"""
        try:
            trade = await trade_service.close_trade(db, trade_id, exit_price)

            # Calculate trade duration
            duration = trade.exit_time - trade.entry_time
            duration_str = str(duration).split('.')[0]  # Remove microseconds

            # Send Telegram notification
            await telegram_service.notify_trade_closed(
                symbol=trade.symbol,
                side=trade.side,
                quantity=trade.quantity,
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                pnl=trade.pnl,
                duration=duration_str
            )

            return trade
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            await telegram_service.notify_error(f"Failed to close trade: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def get_trades(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        symbol: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[trade_schemas.Trade]:
        """Get trades with filters"""
        try:
            return await trade_service.get_trades(
                db, skip=skip, limit=limit, symbol=symbol, status=status
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

trade_controller = TradeController()
