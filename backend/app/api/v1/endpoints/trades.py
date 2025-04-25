from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import crud, schemas
from app.core.database import get_db

router = APIRouter()

@router.get("/", response_model=List[schemas.Trade])
def read_trades(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve trades.
    """
    trades = crud.trade.get_multi(db, skip=skip, limit=limit)
    return trades

@router.post("/", response_model=schemas.Trade)
def create_trade(
    *,
    db: Session = Depends(get_db),
    trade_in: schemas.TradeCreate,
) -> Any:
    """
    Create new trade.
    """
    trade = crud.trade.create(db=db, obj_in=trade_in)
    return trade

@router.get("/{trade_id}", response_model=schemas.Trade)
def read_trade(
    *,
    db: Session = Depends(get_db),
    trade_id: int,
) -> Any:
    """
    Get trade by ID.
    """
    trade = crud.trade.get(db=db, id=trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade

@router.put("/{trade_id}/close", response_model=schemas.Trade)
def close_trade(
    *,
    db: Session = Depends(get_db),
    trade_id: int,
    trade_update: schemas.TradeUpdate,
) -> Any:
    """
    Close a trade.
    """
    trade = crud.trade.get(db=db, id=trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if trade.status == "CLOSED":
        raise HTTPException(status_code=400, detail="Trade is already closed")

    trade.close_trade(trade_update.exit_price)
    db.commit()
    db.refresh(trade)
    return trade
