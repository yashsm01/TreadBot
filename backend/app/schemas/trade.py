from datetime import datetime
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from decimal import Decimal

class TradeBase(BaseModel):
    symbol: str
    side: str
    quantity: float = Field(gt=0)
    entry_price: float = Field(gt=0)
    current_price: float = Field(gt=0)
    take_profit: Optional[float] = Field(gt=0, default=None)
    stop_loss: Optional[float] = Field(gt=0, default=None)
    status: str
    order_type: str = "STOP"
    strategy: Optional[str] = "STRADDLE"
    position_id: Optional[int] = None

    @validator('side')
    def validate_side(cls, v):
        if v not in ["BUY", "SELL"]:
            raise ValueError('side must be either "BUY" or "SELL"')
        return v

    @validator('status')
    def validate_status(cls, v):
        valid_statuses = ["PENDING", "OPEN", "CLOSED", "CANCELLED"]
        if v not in valid_statuses:
            raise ValueError(f'status must be one of {valid_statuses}')
        return v

    @validator('order_type')
    def validate_order_type(cls, v):
        valid_types = ["MARKET", "LIMIT", "STOP"]
        if v not in valid_types:
            raise ValueError(f'order_type must be one of {valid_types}')
        return v

class TradeCreate(TradeBase):
    pass

class TradeResponse(TradeBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    entered_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }

class TradeUpdate(BaseModel):
    exit_price: Optional[float] = Field(gt=0, default=None)
    status: Optional[str] = None
    exit_time: Optional[datetime] = None
    realized_pnl: Optional[float] = None

    @validator('status')
    def validate_status(cls, v):
        if v is not None:
            valid_statuses = ["PENDING", "OPEN", "CLOSED", "CANCELLED"]
            if v not in valid_statuses:
                raise ValueError(f'status must be one of {valid_statuses}')
        return v

class Trade(TradeBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    entered_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    exit_price: Optional[float] = None
    realized_pnl: Optional[float] = None
    unrealized_pnl: Optional[float] = None

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }

class TradingMetrics(BaseModel):
    """Detailed trading metrics for a position"""
    starting_price: float = 0
    current_price: float = 0
    position_size: float = 0
    current_value: float = 0
    profit_loss: float = 0
    profit_loss_percent: float = 0
    buy_profit_percent: Optional[float] = None
    sell_profit_percent: Optional[float] = None
    trend_direction: Optional[str] = None
    trend_strength: Optional[int] = None
    volatility: Optional[float] = None
    profit_threshold: Optional[float] = None
    recent_prices: Optional[List[float]] = None
    buy_trades: List[Dict[str, Any]] = Field(default_factory=list)
    sell_trades: List[Dict[str, Any]] = Field(default_factory=list)

class SwapStatus(BaseModel):
    """Information about coin swap operations"""
    performed: bool = False
    from_coin: str = ""
    to_coin: str = ""
    amount: float = 0
    price: float = 0
    timestamp: Optional[datetime] = None

class TradingStatusResponse(BaseModel):
    """Comprehensive trading status response"""
    status: str
    symbol: str
    reason: Optional[str] = None
    trades: List[Dict[str, Any]] = Field(default_factory=list)
    metrics: TradingMetrics
    swap_status: SwapStatus

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }
