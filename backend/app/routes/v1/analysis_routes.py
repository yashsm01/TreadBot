from typing import Dict, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.controllers.analysis_controller import analysis_controller

router = APIRouter()

@router.get("/market/{symbol}")
async def get_market_analysis(symbol: str) -> Dict:
    """
    Get comprehensive market analysis for a symbol.
    """
    return await analysis_controller.get_market_analysis(symbol)

@router.get("/portfolio")
async def get_portfolio_analysis(
    db: Session = Depends(get_db),
    symbol: Optional[str] = Query(None, description="Filter by trading symbol"),
    days: int = Query(30, description="Number of days for performance analysis")
) -> Dict:
    """
    Get comprehensive portfolio analysis.
    """
    return await analysis_controller.get_portfolio_analysis(
        db=db, symbol=symbol, days=days
    )

@router.get("/trade-check/{symbol}")
async def check_trade_viability(
    symbol: str,
    quantity: float = Query(..., description="Trade quantity"),
    price: float = Query(..., description="Trade price"),
    db: Session = Depends(get_db)
) -> Dict:
    """
    Check if a trade is viable based on risk management and market conditions.
    """
    return await analysis_controller.check_trade_viability(
        db=db,
        symbol=symbol,
        quantity=quantity,
        price=price
    )
