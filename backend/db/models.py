from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import enum
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create declarative base for SQLAlchemy models
Base = declarative_base()

# Enum for trade status
class TradeStatus(enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"

# Enum for trade type (real or paper trading)
class TradeType(enum.Enum):
    REAL = "real"
    PAPER = "paper"

# Trade model for storing trade information
class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    coin = Column(String, index=True)  # Trading pair (e.g., BTC/USDT)
    entry_price = Column(Float)  # Entry price of the trade
    exit_price = Column(Float, nullable=True)  # Exit price (if closed)
    profit_pct = Column(Float, nullable=True)  # Profit/loss percentage
    quantity = Column(Float)  # Trade quantity
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    status = Column(Enum(TradeStatus), default=TradeStatus.OPEN)
    type = Column(Enum(TradeType), default=TradeType.REAL)

# Configuration model for storing trading parameters
class Config(Base):
    __tablename__ = "config"

    id = Column(Integer, primary_key=True, index=True)
    coin = Column(String, unique=True, index=True)  # Trading pair
    interval = Column(String)  # Trading interval (e.g., "5m", "15m", "1h")
    breakout_pct = Column(Float)  # Breakout percentage
    tp_pct = Column(Float)  # Take profit percentage
    sl_pct = Column(Float)  # Stop loss percentage
    quantity = Column(Float)  # Trade quantity
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# Database connection function using environment variable
def get_db_engine():
    """
    Create and return a SQLAlchemy engine using the DATABASE_URL from environment variables.
    The URL format should be: postgresql://username:password@host:port/database
    """
    return create_engine(os.getenv("DATABASE_URL"))
