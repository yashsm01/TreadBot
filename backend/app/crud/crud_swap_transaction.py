from typing import List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from datetime import datetime, timedelta
from app.models.swap_transaction import SwapTransaction
from app.crud.base import CRUDBase
from app.schemas.swap_transaction import SwapTransactionCreate, SwapTransactionUpdate
import logging

logger = logging.getLogger(__name__)

class CRUDSwapTransaction(CRUDBase[SwapTransaction, SwapTransactionCreate, SwapTransactionUpdate]):
    async def get_by_transaction_id(self, db: AsyncSession, transaction_id: str) -> Optional[SwapTransaction]:
        """Get a swap transaction by transaction ID"""
        stmt = select(SwapTransaction).where(SwapTransaction.transaction_id == transaction_id)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_user_id(self, db: AsyncSession, user_id: int,
                             skip: int = 0, limit: int = 100) -> List[SwapTransaction]:
        """Get all swap transactions for a user"""
        stmt = select(SwapTransaction).filter(
            SwapTransaction.user_id == user_id
        ).order_by(SwapTransaction.timestamp.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_symbol(self, db: AsyncSession, symbol: str,
                            user_id: Optional[int] = None,
                            skip: int = 0, limit: int = 100) -> List[SwapTransaction]:
        """Get swap transactions by symbol (either from_symbol or to_symbol)"""
        stmt = select(SwapTransaction).filter(
            (SwapTransaction.from_symbol == symbol) | (SwapTransaction.to_symbol == symbol)
        )

        if user_id:
            stmt = stmt.filter(SwapTransaction.user_id == user_id)

        stmt = stmt.order_by(SwapTransaction.timestamp.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

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

swap_transaction_crud = CRUDSwapTransaction(SwapTransaction)
