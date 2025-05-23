from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
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

    async def get_trades_by_date_range(
        self,
        db: AsyncSession,
        *,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        symbol: Optional[str] = None,
        status: Optional[List[str]] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Trade]:
        """Get trades within a date range"""
        if end_date is None:
            end_date = datetime.now()

        # Look for trades with either entry or exit within the date range
        stmt = select(self.model).where(
            or_(
                and_(
                    Trade.entered_at >= start_date,
                    Trade.entered_at <= end_date
                ),
                and_(
                    Trade.closed_at >= start_date,
                    Trade.closed_at <= end_date
                )
            )
        )

        if symbol:
            stmt = stmt.where(Trade.symbol == symbol)

        if status:
            stmt = stmt.where(Trade.status.in_(status))

        stmt = stmt.order_by(Trade.entered_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_multi_by_position(
        self,
        db: AsyncSession,
        *,
        position_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Trade]:
        """Get all trades for a specific position"""
        stmt = select(self.model).where(
            Trade.position_id == position_id
        ).order_by(Trade.entered_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_profitable_trades(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Trade]:
        """Get trades with positive profit"""
        stmt = select(self.model).where(
            Trade.pnl > 0
        ).order_by(Trade.pnl.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_loss_trades(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Trade]:
        """Get trades with negative profit"""
        stmt = select(self.model).where(
            Trade.pnl < 0
        ).order_by(Trade.pnl.asc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

trade = CRUDTrade(Trade)
