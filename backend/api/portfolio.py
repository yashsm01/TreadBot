from typing import Dict, List, Optional
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..services.portfolio import PortfolioService
from ..db.models import Portfolio, PortfolioTransaction

class PortfolioAPI:
    def __init__(self, db_session: AsyncSession):
        self.portfolio_service = PortfolioService(db_session)

    async def get_portfolio(self, user_id: int) -> Portfolio:
        """Get user's portfolio"""
        try:
            return await self.portfolio_service.get_portfolio(user_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def add_transaction(self, user_id: int, amount: float, transaction_type: str, description: str = None) -> PortfolioTransaction:
        """Add a new transaction"""
        try:
            return await self.portfolio_service.add_transaction(user_id, amount, transaction_type, description)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def get_transactions(self, user_id: int, limit: int = 100) -> List[PortfolioTransaction]:
        """Get portfolio transactions"""
        try:
            return await self.portfolio_service.get_transactions(user_id, limit)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def get_portfolio_summary(self, user_id: int) -> Dict:
        """Get portfolio summary"""
        try:
            return await self.portfolio_service.get_portfolio_summary(user_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
