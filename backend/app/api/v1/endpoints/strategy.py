from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from app import crud, schemas
from app.core.database import get_db
from app.core.config import settings

router = APIRouter()

@router.get("/positions/{strategy_name}", response_model=List[schemas.Position])
async def read_strategy_positions(
    *,
    db: AsyncSession = Depends(get_db),
    strategy_name: str,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Get positions for a specific strategy.
    """
    positions = await crud.position.get_by_strategy(
        db=db, strategy=strategy_name, skip=skip, limit=limit
    )
    return positions

@router.get("/symbols", response_model=List[str])
async def read_trading_symbols() -> Any:
    """
    Get available trading symbols.
    """
    return settings.TRADING_PAIRS
