from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, or_, and_
from datetime import datetime, timedelta
from app.models.swap_transaction import SwapTransaction
from app.crud.base import CRUDBase
from app.schemas.swap_transaction import SwapTransactionCreate, SwapTransactionUpdate
import logging

logger = logging.getLogger(__name__)

class CRUDSwapTransaction(CRUDBase[SwapTransaction, SwapTransactionCreate, SwapTransactionUpdate]):
    async def get_by_transaction_id(self, db: AsyncSession, *, transaction_id: str) -> Optional[SwapTransaction]:
        """Get swap transaction by transaction ID"""
        result = await db.execute(
            select(SwapTransaction).where(SwapTransaction.transaction_id == transaction_id)
        )
        return result.scalars().first()

    async def get_by_user_id(self, db: AsyncSession, *, user_id: int, skip: int = 0, limit: int = 100) -> List[SwapTransaction]:
        """Get swap transactions by user ID"""
        result = await db.execute(
            select(SwapTransaction)
            .where(SwapTransaction.user_id == user_id)
            .offset(skip)
            .limit(limit)
            .order_by(SwapTransaction.timestamp.desc())
        )
        return result.scalars().all()

    async def get_by_symbol(self, db: AsyncSession, *, symbol: str, skip: int = 0, limit: int = 100) -> List[SwapTransaction]:
        """Get swap transactions by symbol (either from_symbol or to_symbol)"""
        result = await db.execute(
            select(SwapTransaction)
            .where(
                or_(
                    SwapTransaction.from_symbol == symbol,
                    SwapTransaction.to_symbol == symbol
                )
            )
            .offset(skip)
            .limit(limit)
            .order_by(SwapTransaction.timestamp.desc())
        )
        return result.scalars().all()

    async def get_by_status(self, db: AsyncSession, status: str,
                           user_id: Optional[int] = None,
                           skip: int = 0, limit: int = 100) -> List[SwapTransaction]:
        """Get swap transactions by status"""
        stmt = select(SwapTransaction).filter(SwapTransaction.status == status)

        if user_id:
            stmt = stmt.filter(SwapTransaction.user_id == user_id)

        stmt = stmt.order_by(SwapTransaction.timestamp.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_transactions(self, db: AsyncSession, days: int = 7,
                                     user_id: Optional[int] = None,
                                     skip: int = 0, limit: int = 100) -> List[SwapTransaction]:
        """Get recent swap transactions within specified days"""
        since_date = datetime.utcnow() - timedelta(days=days)
        stmt = select(SwapTransaction).filter(SwapTransaction.timestamp >= since_date)

        if user_id:
            stmt = stmt.filter(SwapTransaction.user_id == user_id)

        stmt = stmt.order_by(SwapTransaction.timestamp.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_swaps_count_since(self, db: AsyncSession, *, since: datetime) -> int:
        """Count the number of swaps since a specified date"""
        result = await db.execute(
            select(func.count(SwapTransaction.id))
            .where(SwapTransaction.timestamp >= since)
        )
        return result.scalar_one()

    async def get_by_date_range(
        self,
        db: AsyncSession,
        *,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        symbol: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[SwapTransaction]:
        """Get swap transactions within a date range"""
        if end_date is None:
            end_date = datetime.now()

        stmt = select(SwapTransaction).where(
            and_(
                SwapTransaction.timestamp >= start_date,
                SwapTransaction.timestamp <= end_date
            )
        )

        if symbol:
            stmt = stmt.where(
                or_(
                    SwapTransaction.from_symbol == symbol,
                    SwapTransaction.to_symbol == symbol
                )
            )

        stmt = stmt.order_by(SwapTransaction.timestamp.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_position(
        self,
        db: AsyncSession,
        *,
        position_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[SwapTransaction]:
        """Get swap transactions for a specific position"""
        stmt = select(SwapTransaction).where(
            SwapTransaction.position_id == position_id
        ).order_by(SwapTransaction.timestamp.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

swap_transaction_crud = CRUDSwapTransaction(SwapTransaction)
