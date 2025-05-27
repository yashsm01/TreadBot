from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Optional
from app.core.database import get_db
from app.controllers.analysis_controller import analysis_controller
from app.services.helper.binance_helper import binance_helper
from datetime import datetime

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

@router.get("/market/prices/{symbol}", response_model=Dict)
async def get_market_prices(symbol: str):
    """Get historical close prices for a symbol (last 50 5m candles)"""
    try:
        price_history_result = await binance_helper.get_dynamic_price_history(symbol, interval="5m", intervals=50)
        close_prices = [entry["close"] for entry in price_history_result["data"]["history"]]
        return {"symbol": symbol, "close_prices": close_prices}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/straddle/dynamic-levels/{symbol}", response_model=Dict)
async def get_dynamic_straddle_levels(symbol: str, db: AsyncSession = Depends(get_db)):
    """Get enhanced dynamic straddle entry levels based on market volatility"""
    try:
        from app.services.straddle_service import StraddleService, StraddleStrategy

        # Initialize services
        straddle_service = StraddleService(db)
        strategy = StraddleStrategy()

        # Get current price
        current_price_data = await binance_helper.get_current_price(symbol)
        current_price = current_price_data["price"]

        # Fetch historical close prices for volatility calculation
        price_history_result = await binance_helper.get_dynamic_price_history(symbol, interval="5m", intervals=50)
        close_prices = [entry["close"] for entry in price_history_result["data"]["history"]]

        # Calculate volatilities for different timeframes
        # Short-term: last 10 prices (50 minutes)
        short_term_prices = close_prices[-10:] if len(close_prices) >= 10 else close_prices
        # Medium-term: last 20 prices (100 minutes)
        medium_term_prices = close_prices[-20:] if len(close_prices) >= 20 else close_prices
        # Long-term: all available prices
        long_term_prices = close_prices

        short_vol = strategy.calculate_volatility(short_term_prices)
        medium_vol = strategy.calculate_volatility(medium_term_prices)
        long_vol = strategy.calculate_volatility(long_term_prices)

        # Calculate dynamic entry levels
        entry_levels = strategy.calculate_entry_levels_dynamic(
            current_price=current_price,
            short_vol=short_vol,
            medium_vol=medium_vol,
            long_vol=long_vol
        )

        # Add additional market context
        market_context = {
            "symbol": symbol,
            "current_price": current_price,
            "price_history_count": len(close_prices),
            "volatility_analysis": {
                "short_term": {
                    "periods": len(short_term_prices),
                    "volatility": round(short_vol * 100, 4),
                    "price_range": {
                        "min": min(short_term_prices),
                        "max": max(short_term_prices),
                        "spread": round((max(short_term_prices) - min(short_term_prices)) / current_price * 100, 2)
                    }
                },
                "medium_term": {
                    "periods": len(medium_term_prices),
                    "volatility": round(medium_vol * 100, 4),
                    "price_range": {
                        "min": min(medium_term_prices),
                        "max": max(medium_term_prices),
                        "spread": round((max(medium_term_prices) - min(medium_term_prices)) / current_price * 100, 2)
                    }
                },
                "long_term": {
                    "periods": len(long_term_prices),
                    "volatility": round(long_vol * 100, 4),
                    "price_range": {
                        "min": min(long_term_prices),
                        "max": max(long_term_prices),
                        "spread": round((max(long_term_prices) - min(long_term_prices)) / current_price * 100, 2)
                    }
                }
            },
            "entry_levels": entry_levels,
            "recommendations": {
                "preferred_timeframe": "short" if entry_levels["metadata"]["market_condition"] == "high_vol" else "medium" if entry_levels["metadata"]["market_condition"] == "medium_vol" else "long",
                "risk_level": "high" if entry_levels["metadata"]["average_volatility"] > 5 else "medium" if entry_levels["metadata"]["average_volatility"] > 2 else "low",
                "suggested_position_size": "small" if entry_levels["metadata"]["market_condition"] == "high_vol" else "medium" if entry_levels["metadata"]["market_condition"] == "medium_vol" else "large"
            }
        }

        return {
            "success": True,
            "data": market_context,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error calculating dynamic straddle levels for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
