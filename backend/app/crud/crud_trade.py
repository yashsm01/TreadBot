from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.crud.base import CRUDBase
from app.models.trade import Trade
from app.schemas.trade import TradeCreate, TradeUpdate
from datetime import datetime

class CRUDTrade(CRUDBase[Trade, TradeCreate, TradeUpdate]):
    async def get_by_symbol(
        self, db: AsyncSession, *, symbol: str
    ) -> List[Trade]:
        result = await db.execute(
            select(self.model).filter(Trade.symbol == symbol)
        )
        return result.scalars().all()

    async def get_by_position(
        self, db: AsyncSession, *, position_id: int, skip: int = 0, limit: int = 100
    ) -> List[Trade]:
        result = await db.execute(
            select(self.model)
            .filter(Trade.position_id == position_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_open_trades(
        self, db: AsyncSession, *, symbol: Optional[str] = None
    ) -> List[Trade]:
        query = select(self.model).filter(Trade.status == "OPEN")
        if symbol:
            query = query.filter(Trade.symbol == symbol)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_multi_by_symbol_and_status(
        self, db: AsyncSession, *, symbol: str, status: List[str]
    ) -> List[Trade]:
        result = await db.execute(
            select(self.model)
            .filter(Trade.symbol == symbol, Trade.status.in_(status))
        )
        return result.scalars().all()

    async def get_trades_count_since(self, db: AsyncSession, *, since: datetime) -> int:
        """Count the number of trades since a specified date"""
        result = await db.execute(
            select(func.count(Trade.id))
            .where(Trade.entered_at >= since)
        )
        return result.scalar_one()

trade = CRUDTrade(Trade)
