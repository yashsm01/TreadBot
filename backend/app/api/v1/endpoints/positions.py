from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from app import crud, schemas
from app.core.database import get_db

router = APIRouter()

@router.get("/", response_model=List[schemas.Position])
async def read_positions(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    symbol: str = None,
) -> Any:
    """
    Retrieve positions.
    """
    if symbol:
        positions = await crud.position.get_by_symbol(db, symbol=symbol, skip=skip, limit=limit)
    else:
        positions = await crud.position.get_multi(db, skip=skip, limit=limit)
    return positions

@router.post("/", response_model=schemas.Position)
async def create_position(
    *,
    db: AsyncSession = Depends(get_db),
    position_in: schemas.PositionCreate,
) -> Any:
    """
    Create new position.
    """
    position = await crud.position.create(db=db, obj_in=position_in)
    return position

@router.get("/active", response_model=List[schemas.Position])
async def read_active_positions(
    db: AsyncSession = Depends(get_db),
    symbol: str = None,
) -> Any:
    """
    Retrieve active positions.
    """
    positions = await crud.position.get_active_positions(db, symbol=symbol)
    return positions

@router.get("/{position_id}", response_model=schemas.Position)
async def read_position(
    *,
    db: AsyncSession = Depends(get_db),
    position_id: int,
) -> Any:
    """
    Get position by ID.
    """
    position = await crud.position.get(db=db, id=position_id)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    return position

@router.get("/{position_id}/trades", response_model=List[schemas.Trade])
async def read_position_trades(
    *,
    db: AsyncSession = Depends(get_db),
    position_id: int,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Get trades for a specific position.
    """
    position = await crud.position.get(db=db, id=position_id)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    trades = await crud.trade.get_by_position(db, position_id=position_id, skip=skip, limit=limit)
    return trades
