from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import enum
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Create declarative base for SQLAlchemy models
Base = declarative_base()

# Enum for trade status
class TradeStatus(enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"

# Enum for trade type (real or paper trading)
class TradeType(enum.Enum):
    REAL = "REAL"
    PAPER = "PAPER"

# Enum for position type
class PositionType(enum.Enum):
    LONG = "LONG"
    SHORT = "SHORT"

# Trade model for storing trade information
class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    coin = Column(String, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float)
    profit_pct = Column(Float)
    quantity = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(Enum(TradeStatus), nullable=False, default=TradeStatus.OPEN)
    type = Column(Enum(TradeType), nullable=False, default=TradeType.PAPER)
    position = Column(Enum(PositionType), nullable=False, default=PositionType.LONG)

# Configuration model for storing trading parameters
class Config(Base):
    __tablename__ = "config"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Database connection function using environment variable
def get_db_engine():
    """
    Create and return a SQLAlchemy engine using the DATABASE_URL from environment variables.
    The URL format should be: postgresql://username:password@host:port/database
    """
    return create_engine(os.getenv("DATABASE_URL"))
