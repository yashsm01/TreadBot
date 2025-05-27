from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from pydantic import validator


class PortfolioCreate(BaseModel):
    symbol: str
    quantity: float
    avg_buy_price: float
    realized_profit: Optional[float] = 0.0
    asset_type: Optional[str] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    user_id: int = 1

    # Add a validator to ensure we have a proper datetime object
    @validator('last_updated', pre=True)
    def validate_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v


class PortfolioUpdate(BaseModel):
    quantity: Optional[float] = None
    avg_buy_price: Optional[float] = None
    realized_profit: Optional[float] = None
    last_updated: Optional[datetime] = None
    current_price: Optional[float] = None

class PortfolioPosition(BaseModel):
    symbol: str
    quantity: float
    avg_buy_price: float
    current_price: float
    current_value: float
    invested_value: float
    profit_loss: float
    profit_loss_pct: float
    realized_profit: float = 0.0  # Cumulative realized P/L
    unrealized_profit: Optional[float] = None  # Current unrealized P/L
    total_profit: Optional[float] = None  # Realized + Unrealized
    last_updated: datetime

class PortfolioSummary(BaseModel):
    total_invested: float
    total_current_value: float
    total_profit_loss: float
    total_profit_loss_pct: float

class PortfolioResponse(BaseModel):
    portfolio: List[PortfolioPosition]
    summary: PortfolioSummary

class ProfitSummaryResponse(BaseModel):
    timeframe: str
    total_invested: float
    total_current_value: float
    total_profit_loss: float
    total_profit_loss_pct: float
    total_trades: int
    timestamp: datetime

class StraddlePositionResponse(BaseModel):
    position_id: int
    symbol: str
    quantity: float
    strike_price: float
    current_price: float
    open_time: datetime
