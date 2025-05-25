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

    async def get_profit_summary(
        self,
        db: AsyncSession,
        *,
        user_id: Optional[int] = None,
        symbol: Optional[str] = None,
        days: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get profit/loss summary for swap transactions"""
        try:
            stmt = select(SwapTransaction)

            if user_id:
                stmt = stmt.where(SwapTransaction.user_id == user_id)

            if symbol:
                stmt = stmt.where(
                    or_(
                        SwapTransaction.from_symbol == symbol,
                        SwapTransaction.to_symbol == symbol
                    )
                )

            if days:
                since_date = datetime.utcnow() - timedelta(days=days)
                stmt = stmt.where(SwapTransaction.timestamp >= since_date)

            result = await db.execute(stmt)
            transactions = result.scalars().all()

            if not transactions:
                return {
                    "total_swaps": 0,
                    "total_realized_profit": 0.0,
                    "total_fees_paid": 0.0,
                    "average_profit_per_swap": 0.0,
                    "profitable_swaps": 0,
                    "loss_swaps": 0,
                    "profit_percentage": 0.0
                }

            total_realized_profit = sum(getattr(t, 'realized_profit', 0.0) or 0.0 for t in transactions)
            total_fees_paid = sum(t.fee_amount for t in transactions)
            profitable_swaps = len([t for t in transactions if (getattr(t, 'realized_profit', 0.0) or 0.0) > 0])
            loss_swaps = len([t for t in transactions if (getattr(t, 'realized_profit', 0.0) or 0.0) < 0])

            return {
                "total_swaps": len(transactions),
                "total_realized_profit": total_realized_profit,
                "total_fees_paid": total_fees_paid,
                "average_profit_per_swap": total_realized_profit / len(transactions),
                "profitable_swaps": profitable_swaps,
                "loss_swaps": loss_swaps,
                "profit_percentage": (profitable_swaps / len(transactions)) * 100,
                "net_profit_after_fees": total_realized_profit - total_fees_paid
            }

        except Exception as e:
            logger.error(f"Error getting profit summary: {str(e)}")
            return {"error": str(e)}

    async def get_symbol_performance(
        self,
        db: AsyncSession,
        *,
        user_id: Optional[int] = None,
        days: Optional[int] = 30
    ) -> Dict[str, Any]:
        """Get performance breakdown by symbol"""
        try:
            stmt = select(SwapTransaction)

            if user_id:
                stmt = stmt.where(SwapTransaction.user_id == user_id)

            if days:
                since_date = datetime.utcnow() - timedelta(days=days)
                stmt = stmt.where(SwapTransaction.timestamp >= since_date)

            result = await db.execute(stmt)
            transactions = result.scalars().all()

            symbol_performance = {}

            for transaction in transactions:
                # Track both from_symbol and to_symbol
                for symbol in [transaction.from_symbol, transaction.to_symbol]:
                    if symbol not in symbol_performance:
                        symbol_performance[symbol] = {
                            "total_swaps": 0,
                            "total_realized_profit": 0.0,
                            "total_fees": 0.0,
                            "total_volume": 0.0
                        }

                    symbol_performance[symbol]["total_swaps"] += 1
                    symbol_performance[symbol]["total_realized_profit"] += getattr(transaction, 'realized_profit', 0.0) or 0.0
                    symbol_performance[symbol]["total_fees"] += transaction.fee_amount

                    # Add volume (from_amount for from_symbol, to_amount for to_symbol)
                    if symbol == transaction.from_symbol:
                        symbol_performance[symbol]["total_volume"] += transaction.from_amount
                    else:
                        symbol_performance[symbol]["total_volume"] += transaction.to_amount

            # Calculate derived metrics
            for symbol, data in symbol_performance.items():
                data["average_profit_per_swap"] = data["total_realized_profit"] / data["total_swaps"] if data["total_swaps"] > 0 else 0
                data["net_profit"] = data["total_realized_profit"] - data["total_fees"]
                data["profit_percentage"] = (data["total_realized_profit"] / data["total_volume"]) * 100 if data["total_volume"] > 0 else 0

            return symbol_performance

        except Exception as e:
            logger.error(f"Error getting symbol performance: {str(e)}")
            return {"error": str(e)}

swap_transaction_crud = CRUDSwapTransaction(SwapTransaction)
