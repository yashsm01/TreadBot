from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from .trade import Trade

class PositionBase(BaseModel):
    symbol: str
    strategy: str

class PositionCreate(PositionBase):
    pass

class PositionUpdate(BaseModel):
    status: Optional[str] = None

class PositionInDBBase(PositionBase):
    id: int
    total_quantity: float
    average_entry_price: Optional[float] = None
    realized_pnl: float
    unrealized_pnl: float
    status: str
    open_time: datetime
    close_time: Optional[datetime] = None

    class Config:
        from_attributes = True

class Position(PositionInDBBase):
    trades: List[Trade] = []

class PositionInDB(PositionInDBBase):
    pass
