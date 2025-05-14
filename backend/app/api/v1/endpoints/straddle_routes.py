from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.straddle_service import StraddleService, BreakoutSignal
from app.models.trade import Trade
from app.schemas.trade import TradeCreate, TradeResponse
from pydantic import BaseModel, Field, validator
import pandas as pd

router = APIRouter()

class StraddleSetupRequest(BaseModel):
    symbol: str = Field(..., description="Trading pair symbol")
    current_price: float = Field(gt=0, description="Current market price")
    quantity: float = Field(gt=0, description="Trade quantity")

class MarketAnalysisRequest(BaseModel):
    symbol: str = Field(..., description="Trading pair symbol")
    prices: List[float] = Field(..., min_items=10, description="Historical price data")
    volumes: List[float] = Field(..., min_items=10, description="Historical volume data")

    @validator('prices', 'volumes')
    def validate_data_length(cls, v):
        if not all(x > 0 for x in v):
            raise ValueError("All values must be greater than 0")
        return v

class BreakoutRequest(BaseModel):
    symbol: str = Field(..., description="Trading pair symbol")
    direction: str = Field(..., description="Breakout direction (UP/DOWN)")
    price: float = Field(gt=0, description="Breakout price")
    confidence: float = Field(ge=0, le=1, description="Signal confidence level")
    volume_spike: bool = Field(default=False, description="Volume spike indicator")
    bb_squeeze: bool = Field(default=False, description="Bollinger Bands squeeze indicator")
    rsi_divergence: bool = Field(default=False, description="RSI divergence indicator")
    macd_crossover: bool = Field(default=False, description="MACD crossover indicator")

    @validator('direction')
    def validate_direction(cls, v):
        if v not in ["UP", "DOWN"]:
            raise ValueError('direction must be either "UP" or "DOWN"')
        return v

class CloserRequest(BaseModel):
    symbol: str = Field(..., description="Trading pair symbol")

@router.post("/setup/create", response_model=List[TradeResponse])
async def create_straddle_setup(
    setup: StraddleSetupRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new straddle setup for a given symbol.

    Args:
        symbol: Trading pair symbol (e.g. BTC/USDT)
        setup: Setup parameters including current price and quantity
        db: Database session

    Returns:
        List of created trade orders (long and short positions)
    """
    try:
        straddle_service = StraddleService(db)
        trades = await straddle_service.create_straddle_trades(
            symbol=setup.symbol,
            current_price=setup.current_price,
            quantity=setup.quantity
        )
        return trades
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create straddle setup: {str(e)}"
        )

@router.post("/analyze", response_model=Dict[str, Any])
async def analyze_market(
    analysis: MarketAnalysisRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze market conditions for potential breakout.

    Args:
        symbol: Trading pair symbol
        analysis: Analysis parameters including historical prices and volumes
        db: Database session

    Returns:
        Market analysis result including breakout signals and market conditions
    """
    try:
        straddle_service = StraddleService(db)
        symbol = analysis.symbol
        prices_series = pd.Series(analysis.prices)
        volumes_series = pd.Series(analysis.volumes)

        result = await straddle_service.analyze_market_conditions(
            symbol=symbol,
            prices=prices_series,
            volume=volumes_series
        )

        if not result["success"]:
            if result.get("validation_error"):
                raise HTTPException(status_code=400, detail=result["message"])
            raise HTTPException(status_code=500, detail=result["message"])

        if result["has_signal"]:
            signal = result["signal"]
            return {
                "has_signal": True,
                "direction": signal.direction,
                "price": signal.price,
                "confidence": signal.confidence,
                "indicators": {
                    "volume_spike": signal.volume_spike,
                    "rsi_divergence": signal.rsi_divergence,
                    "macd_crossover": signal.macd_crossover,
                    "bb_squeeze": signal.bb_squeeze
                },
                "market_conditions": result["market_conditions"],
                "message": result["message"]
            }

        return {
            "has_signal": False,
            "market_conditions": result["market_conditions"],
            "message": result["message"],
            "reason": result.get("reason", "No breakout conditions met")
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze market conditions: {str(e)}"
        )

@router.post("/breakout", response_model=TradeResponse)
async def handle_breakout_event(
    breakout: BreakoutRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle a breakout event for a given symbol.

    Args:
        symbol: Trading pair symbol
        breakout: Breakout event parameters
        db: Database session

    Returns:
        Activated trade details
    """
    try:
        straddle_service = StraddleService(db)
        breakout_signal = BreakoutSignal(
            symbol=breakout.symbol,
            direction=breakout.direction,
            price=breakout.price,
            confidence=breakout.confidence,
            volume_spike=breakout.volume_spike,
            bb_squeeze = breakout.bb_squeeze,
            rsi_divergence=breakout.rsi_divergence,
            macd_crossover=breakout.macd_crossover
        )

        result = await straddle_service.handle_breakout(
            symbol=breakout.symbol,
            breakout_signal=breakout_signal
        )

        if result:
            return result
        raise HTTPException(
            status_code=404,
            detail="No pending trades found for the symbol"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to handle breakout: {str(e)}"
        )

@router.post("/close", response_model=List[TradeResponse])
async def close_straddle_positions(
    closer: CloserRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Close all open straddle positions for a given symbol.

    Args:
        symbol: Trading pair symbol
        db: Database session

    Returns:
        List of closed trade positions
    """
    try:
        straddle_service = StraddleService(db)
        closed_trades = await straddle_service.close_straddle_trades(closer.symbol)

        if closed_trades:
            return closed_trades
        raise HTTPException(
            status_code=404,
            detail="No open trades found for the symbol"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to close straddle positions: {str(e)}"
        )

@router.post("/auto-buy-sell-straddle-start", response_model=List[TradeResponse])
async def auto_buy_sell_straddle_start(
    params: CloserRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Auto buy or sell straddle based on market conditions
    """
    try:
        straddle_service = StraddleService(db)
        trades = await straddle_service.auto_buy_sell_straddle_start(params.symbol)
        return trades
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to close straddle positions: {str(e)}"
        )

@router.post("/auto-buy-sell-straddle-close", response_model=List[TradeResponse])
async def auto_buy_sell_straddle_close(
    params: CloserRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Auto close straddle position for a given symbol"""
    try:
        straddle_service = StraddleService(db)
        trades = await straddle_service.auto_close_straddle_position(params.symbol)
        return trades
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to close straddle positions: {str(e)}"
        )

@router.post("/auto-buy-sell-straddle-inprogress", response_model=List[TradeResponse])
async def auto_buy_sell_straddle_inprogress(
    params: CloserRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Auto buy or sell straddle based on market conditions"""
    try:
        straddle_service = StraddleService(db)
        trades = await straddle_service.auto_buy_sell_straddle_inprogress(params.symbol)
        return trades
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to close straddle positions: {str(e)}"
        )

