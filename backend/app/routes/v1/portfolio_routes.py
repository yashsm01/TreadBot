from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from ...database import get_db
from ...services.portfolio_service import portfolio_service
from ...schemas.portfolio import (
    TransactionCreate,
    TransactionResponse,
    PortfolioResponse,
    ProfitSummaryResponse,
    StraddlePositionResponse
)

router = APIRouter()

@router.post("/transactions/", response_model=TransactionResponse)
async def create_transaction(
    transaction: TransactionCreate,
    db: Session = Depends(get_db)
):
    """Create a new transaction"""
    try:
        result = await portfolio_service.add_transaction(
            user_id=transaction.user_id,
            symbol=transaction.symbol,
            type=transaction.type,
            quantity=transaction.quantity,
            price=transaction.price
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/transactions/", response_model=List[TransactionResponse])
async def get_transactions(
    user_id: int,
    symbol: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """Get transaction history"""
    try:
        return await portfolio_service.get_transaction_history(
            user_id=user_id,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/summary/{user_id}", response_model=PortfolioResponse)
async def get_portfolio_summary(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get portfolio summary"""
    try:
        return await portfolio_service.get_portfolio_summary(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/profit/{user_id}", response_model=ProfitSummaryResponse)
async def get_profit_summary(
    user_id: int,
    timeframe: str = 'all',
    db: Session = Depends(get_db)
):
    """Get profit/loss summary"""
    try:
        return await portfolio_service.get_profit_summary(user_id, timeframe)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/straddles/{user_id}", response_model=List[StraddlePositionResponse])
async def get_straddle_positions(
    user_id: int,
    symbol: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get straddle positions"""
    try:
        return await portfolio_service.get_straddle_positions(user_id, symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
