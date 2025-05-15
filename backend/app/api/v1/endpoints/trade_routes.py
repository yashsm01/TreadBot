from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict
from ....core.database import get_db
from ....services.portfolio_service import portfolio_service

router = APIRouter()

@router.get("/", response_model=List[Dict])
async def get_trades(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    """Get all trades"""
    try:
        return await portfolio_service.get_trades(skip=skip, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{trade_id}", response_model=Dict)
async def get_trade(
    trade_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific trade by ID"""
    try:
        trade = await portfolio_service.get_trade(trade_id)
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")
        return trade
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
