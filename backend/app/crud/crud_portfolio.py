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

    # Override the create method to ensure proper datetime handling
    async def create(self, db: AsyncSession, *, obj_in: PortfolioCreate) -> Portfolio:
        """Create a new portfolio with proper datetime handling"""
        obj_in = PortfolioCreate(**obj_in)
        # Convert any string dates to proper datetime objects
        if isinstance(obj_in.last_updated, str):
            obj_in.last_updated = datetime.fromisoformat(obj_in.last_updated.replace('Z', '+00:00'))

        # Create dict of values for SQLAlchemy model
        db_obj = Portfolio(
            symbol=obj_in.symbol,
            quantity=obj_in.quantity,
            avg_buy_price=obj_in.avg_buy_price,
            realized_profit=obj_in.realized_profit or 0.0,
            asset_type=obj_in.asset_type,
            user_id=obj_in.user_id,
            last_updated=obj_in.last_updated
        )

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update_realized_profit(
        self,
        db: AsyncSession,
        portfolio: Portfolio,
        profit_amount: float
    ) -> Portfolio:
        """Update the realized profit for a portfolio"""
        current_profit = getattr(portfolio, 'realized_profit', 0.0) or 0.0
        portfolio.realized_profit = current_profit + profit_amount
        portfolio.last_updated = helpers.get_current_ist_for_db()

        db.add(portfolio)
        await db.commit()
        await db.refresh(portfolio)
        return portfolio

    async def get_portfolio_with_profit_summary(
        self,
        db: AsyncSession,
        user_id: int = 1
    ) -> Dict:
        """Get portfolio summary including realized and unrealized profits"""
        try:
            portfolios = await self.get_user_portfolio(db, user_id=user_id, active_only=False)

            total_realized_profit = 0.0
            total_unrealized_profit = 0.0
            total_invested = 0.0
            total_current_value = 0.0

            portfolio_details = []

            for portfolio in portfolios:
                realized_profit = getattr(portfolio, 'realized_profit', 0.0) or 0.0
                total_realized_profit += realized_profit

                if portfolio.quantity > 0:
                    invested_value = portfolio.quantity * portfolio.avg_buy_price
                    total_invested += invested_value

                    # Note: You'll need to get current price from price service
                    # For now, we'll use avg_buy_price as placeholder
                    current_value = portfolio.quantity * portfolio.avg_buy_price
                    total_current_value += current_value

                    unrealized_profit = current_value - invested_value
                    total_unrealized_profit += unrealized_profit

                    portfolio_details.append({
                        "symbol": portfolio.symbol,
                        "quantity": portfolio.quantity,
                        "avg_buy_price": portfolio.avg_buy_price,
                        "realized_profit": realized_profit,
                        "unrealized_profit": unrealized_profit,
                        "total_profit": realized_profit + unrealized_profit
                    })

            return {
                "portfolios": portfolio_details,
                "summary": {
                    "total_invested": total_invested,
                    "total_current_value": total_current_value,
                    "total_realized_profit": total_realized_profit,
                    "total_unrealized_profit": total_unrealized_profit,
                    "total_profit": total_realized_profit + total_unrealized_profit,
                    "total_profit_percentage": (total_realized_profit + total_unrealized_profit) / total_invested * 100 if total_invested > 0 else 0
                }
            }

        except Exception as e:
            logger.error(f"Error getting portfolio profit summary: {str(e)}")
            return {"portfolios": [], "summary": {}}


# Create instances
portfolio_crud = CRUDPortfolio(Portfolio)

