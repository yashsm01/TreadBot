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

class TransactionUpdate(TransactionBase):
    pass

class TransactionResponse(TransactionBase):
    id: int
    total: float
    timestamp: datetime

    class Config:
        from_attributes = True

