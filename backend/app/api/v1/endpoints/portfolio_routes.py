from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Optional
from app.core.database import get_db
from app.services.portfolio_service import portfolio_service
from app.crud.crud_portfolio import portfolio_crud

router = APIRouter()

@router.get("/", response_model=Dict)
async def get_portfolio_summary(
    db: AsyncSession = Depends(get_db)
):
    """Get portfolio summary"""
    try:
        return await portfolio_service.get_portfolio_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/positions", response_model=List[Dict])
async def get_positions(
    db: AsyncSession = Depends(get_db),
    symbol: Optional[str] = None
):
    """Get all positions"""
    try:
        return await portfolio_service.get_positions(symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/positions/{position_id}", response_model=Dict)
async def get_position(
    position_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific position by ID"""
    try:
        position = await portfolio_service.get_position(position_id)
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")
        return position
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/straddles", response_model=List[Dict])
async def get_straddle_positions(
    db: AsyncSession = Depends(get_db),
    symbol: Optional[str] = None
):
    """Get straddle positions"""
    try:
        return await portfolio_service.get_straddle_positions(symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/profit-summary", response_model=Dict)
async def get_portfolio_profit_summary(
    user_id: int = 1,
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive profit/loss summary for the portfolio including realized and unrealized profits
    """
    try:
        summary = await portfolio_crud.get_portfolio_with_profit_summary(db, user_id=user_id)
        return {
            "status": "success",
            "data": summary
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get profit summary: {str(e)}"
        )

@router.get("/realized-profit/{symbol}")
async def get_symbol_realized_profit(
    symbol: str,
    user_id: int = 1,
    db: AsyncSession = Depends(get_db)
):
    """
    Get realized profit for a specific symbol
    """
    try:
        portfolio = await portfolio_crud.get_by_user_and_symbol(db, symbol=symbol, user_id=user_id)
        if not portfolio:
            raise HTTPException(status_code=404, detail=f"Portfolio for {symbol} not found")

        realized_profit = getattr(portfolio, 'realized_profit', 0.0) or 0.0

        return {
            "status": "success",
            "data": {
                "symbol": symbol,
                "realized_profit": realized_profit,
                "quantity": portfolio.quantity,
                "avg_buy_price": portfolio.avg_buy_price,
                "last_updated": portfolio.last_updated
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get realized profit for {symbol}: {str(e)}"
        )
