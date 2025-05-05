from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from ....core.database import get_db
from ....services.portfolio_service import portfolio_service

router = APIRouter()

@router.get("/", response_model=Dict)
async def get_portfolio_summary(
    db: Session = Depends(get_db)
):
    """Get portfolio summary"""
    try:
        return await portfolio_service.get_portfolio_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/positions", response_model=List[Dict])
async def get_positions(
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db)
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
    db: Session = Depends(get_db),
    symbol: Optional[str] = None
):
    """Get straddle positions"""
    try:
        return await portfolio_service.get_straddle_positions(symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
