from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Optional

from ..api.portfolio import PortfolioAPI
from ..db.database import get_db
from ..db.models import Portfolio, PortfolioTransaction
from ..auth.auth import get_current_user

router = APIRouter()

@router.get("/portfolio", response_model=Portfolio)
async def get_portfolio(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's portfolio"""
    portfolio_api = PortfolioAPI(db)
    return await portfolio_api.get_portfolio(current_user["id"])

@router.post("/portfolio/transaction", response_model=PortfolioTransaction)
async def add_transaction(
    amount: float,
    transaction_type: str,
    description: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add a new transaction to portfolio"""
    portfolio_api = PortfolioAPI(db)
    return await portfolio_api.add_transaction(
        current_user["id"],
        amount,
        transaction_type,
        description
    )

@router.get("/portfolio/transactions", response_model=List[PortfolioTransaction])
async def get_transactions(
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get portfolio transactions"""
    portfolio_api = PortfolioAPI(db)
    return await portfolio_api.get_transactions(current_user["id"], limit)

@router.get("/portfolio/summary", response_model=Dict)
async def get_portfolio_summary(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get portfolio summary"""
    portfolio_api = PortfolioAPI(db)
    return await portfolio_api.get_portfolio_summary(current_user["id"])
