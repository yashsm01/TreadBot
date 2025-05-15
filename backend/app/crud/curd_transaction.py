from typing import List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from datetime import datetime, timedelta
from app.models.transaction import Transaction
from app.crud.base import CRUDBase
from app.services.helper.heplers import helpers
from app.schemas.transaction import   TransactionCreate, TransactionUpdate
import logging

logger = logging.getLogger(__name__)

class CRUDTransaction(CRUDBase[Transaction, TransactionCreate , TransactionUpdate]):
    async def create_transaction(
        self,
        db: AsyncSession,
        user_id: int,
        portfolio_id: int,
        symbol: str,
        type: str,
        quantity: float,
        price: float
    ) -> Transaction:
        """Create a new transaction"""
        transaction = Transaction(
            user_id=user_id,
            portfolio_id=portfolio_id,
            symbol=symbol,
            type=type.upper(),
            quantity=quantity,
            price=price,
            total=quantity * price,
            timestamp=helpers.get_current_ist_for_db()
        )
        db.add(transaction)
        await db.commit()
        await db.refresh(transaction)
        return transaction

    async def get_user_transactions(
        self,
        db: AsyncSession,
        user_id: int,
        symbol: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Transaction]:
        """Get user's transaction history with optional filters"""
        stmt = select(Transaction).filter(Transaction.user_id == user_id)

        if symbol:
            stmt = stmt.filter(Transaction.symbol == symbol)
        if start_date:
            stmt = stmt.filter(Transaction.timestamp >= start_date)
        if end_date:
            stmt = stmt.filter(Transaction.timestamp <= end_date)

        stmt = stmt.order_by(Transaction.timestamp.desc()).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_profit_summary(
        self,
        db: AsyncSession,
        user_id: int,
        timeframe: str = 'all'
    ) -> Dict:
        """Get profit summary for specified timeframe"""
        stmt = select(
            func.sum(Transaction.total).label('total_invested'),
            func.count().label('total_trades')
        ).filter(Transaction.user_id == user_id)

        if timeframe != 'all':
            now = datetime.utcnow()
            if timeframe == 'daily':
                start_date = now - timedelta(days=1)
            elif timeframe == 'weekly':
                start_date = now - timedelta(days=7)
            elif timeframe == 'monthly':
                start_date = now - timedelta(days=30)
            stmt = stmt.filter(Transaction.timestamp >= start_date)

        result = await db.execute(stmt)
        row = result.fetchone()
        return {
            'total_invested': row.total_invested or 0,
            'total_trades': row.total_trades or 0
        }

    async def get_straddle_transactions(
        self,
        db: AsyncSession,
        user_id: int,
        symbol: Optional[str] = None
    ) -> List[Transaction]:
        """Get straddle transactions for a user"""
        stmt = select(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.type.in_(['BUY', 'SELL'])
        )

        if symbol:
            stmt = stmt.filter(Transaction.symbol == symbol)

        stmt = stmt.order_by(Transaction.timestamp.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

transaction_crud = CRUDTransaction(Transaction)
