from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class PortfolioCreate(BaseModel):
    symbol: str
    quantity: float
    avg_buy_price: float
    last_updated: datetime
    asset_type: str
    entry_price: float
    last_updated: datetime


class PortfolioUpdate(BaseModel):
    quantity: float
    avg_buy_price: float

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
