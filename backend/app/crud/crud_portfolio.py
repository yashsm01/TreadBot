from typing import List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from datetime import datetime, timedelta
from app.models.portfolio import Portfolio
from app.crud.base import CRUDBase
from app.services.helper.heplers import helpers
from app.schemas.portfolio import PortfolioCreate, PortfolioUpdate
import logging

logger = logging.getLogger(__name__)

class CRUDPortfolio(CRUDBase[Portfolio, PortfolioCreate, PortfolioUpdate]):

    async def get_by_user_and_symbol(self, db: AsyncSession, symbol: str, user_id: int = 1) -> Optional[Portfolio]:
        """Get portfolio by user ID and symbol"""
        try:
            stmt = select(Portfolio).where(
                Portfolio.symbol == symbol,
                Portfolio.user_id == user_id
            ).order_by(Portfolio.id.desc())
            result = await db.execute(stmt)
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error in get_by_user_and_symbol: {str(e)}")
            return None

    async def get_all_for_user(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Portfolio]:
        """Get all portfolios for a specific user"""
        stmt = select(Portfolio).order_by(Portfolio.id).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def find_or_create(self, db: AsyncSession, symbol: str, obj_in: PortfolioCreate) -> Portfolio:
        """Find existing portfolio or create a new one"""
        portfolio = await self.get_by_user_and_symbol(db, symbol=symbol)
        if portfolio:
            return portfolio
        return await self.create(db, obj_in=obj_in)

    async def get_user_portfolio(self, db: AsyncSession, user_id: int, active_only: bool = True) -> List[Portfolio]:
        """Get all portfolio entries for a user"""
        stmt = select(Portfolio).filter(Portfolio.user_id == user_id)
        if active_only:
            stmt = stmt.filter(Portfolio.quantity > 0)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def update_portfolio(
        self,
        db: AsyncSession,
        portfolio: Portfolio,
        type: str,
        quantity: float,
        price: float
    ) -> Portfolio:
        """Update portfolio with new transaction"""
        if type.upper() == 'BUY':
            total_value = (portfolio.quantity * portfolio.avg_buy_price) + (quantity * price)
            new_quantity = portfolio.quantity + quantity
            portfolio.avg_buy_price = total_value / new_quantity if new_quantity > 0 else price
            portfolio.quantity = new_quantity
        else:  # SELL
            portfolio.quantity -= quantity

        portfolio.last_updated = helpers.get_current_ist_for_db()
        db.add(portfolio)
        await db.commit()
        await db.refresh(portfolio)
        return portfolio


# Create instances
portfolio_crud = CRUDPortfolio(Portfolio)

