from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, func
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import os
import sys

# Add the parent directory to sys.path
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from database import Base

class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    symbol = Column(String, nullable=False)
    quantity = Column(Float, nullable=False, default=0)
    avg_buy_price = Column(Float, nullable=False)
    last_updated = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    symbol = Column(String, nullable=False)
    type = Column(String, nullable=False)  # BUY or SELL
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False, server_default=func.now())

class StraddleInterval(Base):
    __tablename__ = "straddle_intervals"

    id = Column(Integer, primary_key=True)
    position_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    user_id = Column(Integer, nullable=False)
    interval_minutes = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationship to the transaction
    transaction = relationship("Transaction")
