from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
import os
import sys

# Add the parent directory to sys.path
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from database import Base

class Portfolio(Base):
    __tablename__ = "portfolio"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    symbol = Column(String, index=True)
    quantity = Column(Float)
    avg_buy_price = Column(Float)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    symbol = Column(String, index=True)
    type = Column(String)  # 'BUY' or 'SELL'
    quantity = Column(Float)
    price = Column(Float)
    total = Column(Float)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
