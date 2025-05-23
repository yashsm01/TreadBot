from typing import List, Dict, Any, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.crud.base import CRUDBase
from app.models.position import Position
from app.schemas.position import PositionCreate, PositionUpdate
from sqlalchemy import select, and_, between
from pydantic import BaseModel, Field, validator
from datetime import datetime

class CRUDPosition(CRUDBase[Position, PositionCreate, PositionUpdate]):
    async def insert_position(self, db: AsyncSession, position: Position) -> Position:
        db.add(position)
        await db.commit()
        await db.refresh(position)
        return position

    async def get_position_by_symbol(self, db: AsyncSession, symbol: str) -> Optional[Position]:
        result = await db.execute(select(Position).where(Position.symbol == symbol))
        return result.scalar_one_or_none()

    async def get_open_positions(self, db: AsyncSession) -> List[Position]:
        result = await db.execute(select(Position).where(Position.status == "OPEN"))
        return list(result.scalars().all())

    async def get_closed_positions(self, db: AsyncSession) -> List[Position]:
        result = await db.execute(select(Position).where(Position.status == "CLOSED"))
        return list(result.scalars().all())

    async def get_by_symbol_and_status(
        self, db: AsyncSession, *, symbol: str, status: Union[str, List[str]]
    ) -> Optional[Position]:
        """Get a position by symbol and status"""
        stmt = select(Position).where(
            Position.symbol == symbol,
        )

        if isinstance(status, list):
            stmt = stmt.where(Position.status.in_(status))
        else:
            stmt = stmt.where(Position.status == status)

        stmt = stmt.order_by(Position.id.desc()).limit(1)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_status(self, db: AsyncSession, status: str) -> List[Position]:
        result = await db.execute(select(Position).where(Position.status == status))
        return list(result.scalars().all())

    async def update_position(self, db: AsyncSession, position: Position) -> Position:
        position_data = position.model_dump()
        for key, value in position_data.items():
            setattr(position, key, value)
        db.add(position)
        await db.commit()
        await db.refresh(position)
        return position

    async def get_position_by_symbol(
        self, db: AsyncSession, *, symbol: str
    ) -> Optional[Position]:
        """Get the latest position for a symbol"""
        stmt = select(Position).where(
            Position.symbol == symbol
        ).order_by(Position.id.desc()).limit(1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_positions(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[Position]:
        """Get all positions"""
        stmt = select(Position).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_active_positions(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[Position]:
        """Get all open positions"""
        stmt = select(Position).where(
            Position.status.in_(["OPEN", "IN_PROGRESS"])
        ).order_by(Position.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_positions_by_date_range(
        self,
        db: AsyncSession,
        *,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        symbol: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Position]:
        """Get positions created within a date range"""
        if end_date is None:
            end_date = datetime.now()

        stmt = select(Position).where(
            and_(
                Position.created_at >= start_date,
                Position.created_at <= end_date
            )
        )

        if symbol:
            stmt = stmt.where(Position.symbol == symbol)

        stmt = stmt.order_by(Position.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_position_profit(
        self,
        db: AsyncSession,
        *,
        position_id: int
    ) -> Optional[float]:
        """Get the realized profit for a position"""
        position = await self.get(db, id=position_id)
        if not position:
            return None

        return position.realized_pnl

position_crud = CRUDPosition(Position)



