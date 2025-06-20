from sqlalchemy import Column, Integer, String, Float, DateTime, func, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class SwapTransaction(Base):
    __tablename__ = "swap_transactions"

    id = Column(Integer, primary_key=True)
    transaction_id = Column(String, unique=True, nullable=False)
    from_symbol = Column(String, nullable=False)
    to_symbol = Column(String, nullable=False)
    from_amount = Column(Float, nullable=False)
    to_amount = Column(Float, nullable=False)
    rate = Column(Float, nullable=False)
    fee_percentage = Column(Float, nullable=False)
    fee_amount = Column(Float, nullable=False)
    realized_profit = Column(Float, default=0.0, nullable=False)  # Realized P/L for this swap
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String, nullable=False)  # "completed", "failed", "pending"
    user_id = Column(Integer, nullable=False, default=1)
    position_id = Column(Integer, nullable=False)
    to_stable = Column(Boolean, nullable=False, default=False)
