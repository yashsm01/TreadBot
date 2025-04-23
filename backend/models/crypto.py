from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.sql import func
from ..database import Base

class Cryptocurrency(Base):
    __tablename__ = "cryptocurrencies"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True)  # e.g., "BTC/USDT"
    name = Column(String)  # e.g., "Bitcoin"
    is_active = Column(Boolean, default=True)
    min_quantity = Column(Float)  # Minimum trade quantity
    price_precision = Column(Integer)  # Number of decimal places for price
    quantity_precision = Column(Integer)  # Number of decimal places for quantity
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Cryptocurrency(symbol={self.symbol}, name={self.name})>"

    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "name": self.name,
            "is_active": self.is_active,
            "min_quantity": self.min_quantity,
            "price_precision": self.price_precision,
            "quantity_precision": self.quantity_precision,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
