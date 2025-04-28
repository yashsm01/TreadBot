from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.controllers.trade_controller import trade_controller
from backend.app.schemas import trade as trade_schemas

router = APIRouter()

@router.post("/", response_model=trade_schemas.Trade)
async def create_trade(
    trade_data: trade_schemas.TradeCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new trade.
    """
    return await trade_controller.create_trade(db=db, trade_data=trade_data)

@router.get("/", response_model=List[trade_schemas.Trade])
async def get_trades(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    symbol: Optional[str] = Query(None, description="Filter by trading symbol"),
    status: Optional[str] = Query(None, description="Filter by trade status (OPEN/CLOSED)")
):
    """
    Get list of trades with optional filters.
    """
    return await trade_controller.get_trades(
        db=db, skip=skip, limit=limit, symbol=symbol, status=status
    )

@router.get("/{trade_id}", response_model=trade_schemas.Trade)
async def get_trade(trade_id: int, db: Session = Depends(get_db)):
    """
    Get a specific trade by ID.
    """
    trades = await trade_controller.get_trades(db=db, skip=0, limit=1)
    if not trades:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trades[0]

@router.put("/{trade_id}/close", response_model=trade_schemas.Trade)
async def close_trade(
    trade_id: int,
    trade_update: trade_schemas.TradeUpdate,
    db: Session = Depends(get_db)
):
    """
    Close a specific trade.
    """
    return await trade_controller.close_trade(
        db=db,
        trade_id=trade_id,
        exit_price=trade_update.exit_price
    )
