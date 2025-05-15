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
    status: str
    user_id: int = 1

class SwapTransactionCreate(SwapTransactionBase):
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class SwapTransactionUpdate(BaseModel):
    status: Optional[str] = None

class SwapTransactionInDB(SwapTransactionBase):
    id: int
    timestamp: datetime

    class Config:
        orm_mode = True

class SwapTransaction(SwapTransactionInDB):
    pass
