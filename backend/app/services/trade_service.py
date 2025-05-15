from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.crud.crud_trade import trade as trade_crud
from app.crud.curd_position import position_crud as position_crud
from app.schemas import trade as trade_schemas
from app.schemas import position as position_schemas
from app.core.logger import logger
from datetime import datetime

class TradeService:
    @staticmethod
    async def create_trade(db: AsyncSession, trade_data: trade_schemas.TradeCreate) -> trade_schemas.Trade:
        """Create a new trade and update associated position"""
        try:
            # Create trade
            trade = await trade_crud.create(db=db, obj_in=trade_data)

            # Create or update position
            position = await position_crud.get_by_status(db=db, status="OPEN")
            if not position:
                position_data = position_schemas.PositionCreate(
                    symbol=trade.symbol,
                    strategy="TIME_BASED_STRADDLE",
                )
                position = await position_crud.create(db=db, obj_in=position_data)

            # Associate trade with position
            trade.position_id = position.id
            db.add(trade)
            await db.commit()
            await db.refresh(trade)

            return trade
        except Exception as e:
            logger.error(f"Error creating trade: {str(e)}")
            raise

    @staticmethod
    async def close_trade(
        db: AsyncSession, trade_id: int, exit_price: float
    ) -> trade_schemas.Trade:
        """Close a trade and update position"""
        try:
            trade = await trade_crud.get(db=db, id=trade_id)
            if not trade:
                raise ValueError("Trade not found")
            if trade.status == "CLOSED":
                raise ValueError("Trade already closed")

            trade.close_trade(exit_price)
            db.add(trade)
            await db.commit()
            await db.refresh(trade)

            # Update position metrics
            if trade.position:
                trade.position.update_position_metrics()
                db.add(trade.position)
                await db.commit()
                await db.refresh(trade.position)

            return trade
        except Exception as e:
            logger.error(f"Error closing trade: {str(e)}")
            raise

    @staticmethod
    async def get_trades(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        symbol: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[trade_schemas.Trade]:
        """Get trades with filters"""
        try:
            stmt = select(trade_crud.model)

            if symbol:
                stmt = stmt.filter(trade_crud.model.symbol == symbol)
            if status:
                stmt = stmt.filter(trade_crud.model.status == status)

            stmt = stmt.offset(skip).limit(limit)
            result = await db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching trades: {str(e)}")
            raise

trade_service = TradeService()
