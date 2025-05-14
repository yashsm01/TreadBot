from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.crud.base import CRUDBase
from app.models.position import Position
from app.schemas.position import PositionCreate, PositionUpdate
from sqlalchemy import select
from pydantic import BaseModel, Field, validator

class CRUDPosition(CRUDBase[Position, PositionCreate, PositionUpdate]):
    async def insert_position(self, db: AsyncSession, position: Position) -> Position:
        db.add(position)
        await db.commit()
        await db.refresh(position)
        return position

    async def get_position_by_symbol(self, db: AsyncSession, symbol: str) -> Position:
        result = await db.execute(select(Position).where(Position.symbol == symbol))
        return result.scalars().first()

    async def get_open_positions(self, db: AsyncSession) -> List[Position]:
        return await db.execute(select(Position).where(Position.status == "OPEN"))

    async def get_closed_positions(self, db: AsyncSession) -> List[Position]:
        return await db.execute(select(Position).where(Position.status == "CLOSED"))

    async def get_by_symbol_and_status(self, db: AsyncSession, symbol: str, status: str) -> List[Position]:
        result = await db.execute(select(Position).where(Position.symbol == symbol, Position.status == status))
        return result.scalars().first()

    async def get_by_status(self, db: AsyncSession, status: str) -> List[Position]:
        return await db.execute(select(Position).where(Position.status == status))

    async def update_position(self, db: AsyncSession, position: Position) -> Position:
        position_data = position.model_dump()
        for key, value in position_data.items():
            setattr(position, key, value)
        db.add(position)
        await db.commit()
        await db.refresh(position)
        return position

position_crud = CRUDPosition(Position)



