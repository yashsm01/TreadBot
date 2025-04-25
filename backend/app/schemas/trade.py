from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class TradeBase(BaseModel):
    symbol: str
    side: str
    quantity: float
    entry_price: float
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    status: str = "OPEN"
    strategy: Optional[str] = None
    position_id: Optional[int] = None

class TradeCreate(TradeBase):
    pass

class TradeUpdate(BaseModel):
    exit_price: Optional[float] = None
    status: Optional[str] = None
    exit_time: Optional[datetime] = None
    realized_pnl: Optional[float] = None

class Trade(TradeBase):
    id: int
    entry_time: datetime
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    realized_pnl: Optional[float] = None
    unrealized_pnl: Optional[float] = None

    class Config:
        from_attributes = True
