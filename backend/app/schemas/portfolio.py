from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class TransactionBase(BaseModel):
    user_id: int
    symbol: str
    type: str = Field(..., description="BUY or SELL")
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)

class TransactionCreate(TransactionBase):
    pass

class TransactionResponse(TransactionBase):
    id: int
    total: float
    timestamp: datetime

    class Config:
        from_attributes = True

class PortfolioPosition(BaseModel):
    symbol: str
    quantity: float
    avg_buy_price: float
    current_price: float
    current_value: float
    invested_value: float
    profit_loss: float
    profit_loss_pct: float
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
