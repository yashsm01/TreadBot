from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.sql import func
from ..database import Base

class Cryptocurrency(Base):
    __tablename__ = "cryptocurrencies"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True)
    name = Column(String)
    current_price = Column(Float)
    market_cap = Column(Float)
    volume_24h = Column(Float)
    price_change_24h = Column(Float)
    price_change_percentage_24h = Column(Float)
    min_quantity = Column(Float)
    price_precision = Column(Integer)
    quantity_precision = Column(Integer)
    last_updated = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<Cryptocurrency(symbol={self.symbol}, name={self.name}, current_price={self.current_price})>"

class CryptoPair(Base):
    __tablename__ = "crypto_pairs"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, unique=True, nullable=False, index=True)
    base_currency = Column(String)
    quote_currency = Column(String)
    min_quantity = Column(Float)
    max_quantity = Column(Float)
    price_precision = Column(Integer)
    quantity_precision = Column(Integer)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<CryptoPair(symbol='{self.symbol}', active={self.is_active})>"
