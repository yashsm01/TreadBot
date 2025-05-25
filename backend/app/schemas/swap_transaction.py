from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class SwapTransactionBase(BaseModel):
    transaction_id: str
    from_symbol: str
    to_symbol: str
    from_amount: float
    to_amount: float
    rate: float
    fee_percentage: float
    fee_amount: float
    realized_profit: float = 0.0  # Realized P/L for this swap
    status: str
    user_id: int = 1
    position_id: Optional[int] = None
    to_stable: Optional[bool] = False

class SwapTransactionCreate(SwapTransactionBase):
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class SwapTransactionUpdate(BaseModel):
    status: Optional[str] = None
    realized_profit: Optional[float] = None

class SwapTransactionInDB(SwapTransactionBase):
    id: int
    timestamp: datetime

    class Config:
        orm_mode = True

class SwapTransaction(SwapTransactionInDB):
    pass

# Additional schemas for enhanced P/L tracking
class SwapTransactionWithProfitLoss(SwapTransactionInDB):
    """Extended swap transaction with calculated profit/loss metrics"""
    profit_percentage: Optional[float] = None
    cumulative_profit: Optional[float] = None
    avg_buy_price: Optional[float] = None

class SwapProfitSummary(BaseModel):
    """Summary of profit/loss across multiple swaps"""
    total_swaps: int
    total_realized_profit: float
    total_fees_paid: float
    best_performing_symbol: Optional[str] = None
    worst_performing_symbol: Optional[str] = None
    average_profit_per_swap: float
    profit_percentage: float
