from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Optional
from app.core.database import get_db
from app.controllers.analysis_controller import analysis_controller

router = APIRouter()

@router.get("/market/{symbol}", response_model=Dict)
async def get_market_analysis(symbol: str):
    """Get comprehensive market analysis for a symbol"""
    try:
        return await analysis_controller.get_market_analysis(symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/portfolio", response_model=Dict)
async def get_portfolio_analysis(
    db: AsyncSession = Depends(get_db),
    symbol: Optional[str] = Query(None, description="Filter by trading symbol"),
    days: int = Query(30, description="Number of days for performance analysis")
):
    """Get comprehensive portfolio analysis"""
    try:
        return await analysis_controller.get_portfolio_analysis(
            db=db, symbol=symbol, days=days
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trade-check/{symbol}", response_model=Dict)
async def check_trade_viability(
    symbol: str,
    quantity: float = Query(..., description="Trade quantity"),
    price: float = Query(..., description="Trade price"),
    db: AsyncSession = Depends(get_db)
):
    """Check if a trade is viable based on risk management and market conditions"""
    try:
        return await analysis_controller.check_trade_viability(
            db=db,
            symbol=symbol,
            quantity=quantity,
            price=price
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
