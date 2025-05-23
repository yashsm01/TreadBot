from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Optional
from datetime import datetime, timedelta
from app.core.database import get_db
from app.services.profit_service import profit_service

router = APIRouter()

@router.get("/position/{position_id}", response_model=Dict)
async def get_position_profit(
    position_id: int,
    include_swaps: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """Calculate profit for a specific position"""
    try:
        # Initialize service with database session
        profit_service.db = db

        # Get profit for the position
        result = await profit_service.get_position_profit(
            position_id=position_id,
            include_swaps=include_swaps
        )

        if "error" in result and not result.get("position_id"):
            raise HTTPException(status_code=404, detail=result["error"])

        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/date-range", response_model=Dict)
async def get_profit_by_date_range(
    start_date: datetime = Query(None, description="Start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO format, defaults to now)"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    days: Optional[int] = Query(None, description="Number of days to look back (alternative to start_date)"),
    db: AsyncSession = Depends(get_db)
):
    """Calculate profit for a date range"""
    try:
        # Initialize service with database session
        profit_service.db = db

        # Handle different ways to specify the date range
        if not start_date and days:
            start_date = datetime.now() - timedelta(days=days)
        elif not start_date:
            # Default to 7 days if neither start_date nor days is provided
            start_date = datetime.now() - timedelta(days=7)

        # Get profit for the date range
        result = await profit_service.get_profit_by_date_range(
            start_date=start_date,
            end_date=end_date,
            symbol=symbol
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/summary", response_model=Dict)
async def get_profit_summary(
    db: AsyncSession = Depends(get_db)
):
    """Get an overall profit summary"""
    try:
        # Initialize service with database session
        profit_service.db = db

        # Get profit summary
        result = await profit_service.get_profit_summary()

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
