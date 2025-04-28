from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from ..database import Base

class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    symbol = Column(String, nullable=False)
    quantity = Column(Float, default=0)
    avg_buy_price = Column(Float, nullable=False)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    transactions = relationship("Transaction", back_populates="portfolio")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"))
    symbol = Column(String, nullable=False)
    type = Column(String, nullable=False)  # BUY or SELL
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    portfolio = relationship("Portfolio", back_populates="transactions")
