from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional, List, Union, Any, Literal
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum as SQLAlchemyEnum
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Define valid status values
StatusType = Literal["OPEN", "CLOSED"]

class PositionBase(BaseModel):
    """Base Pydantic model for Position"""
    symbol: str
    strategy: str = "TIME_BASED_STRADDLE"
    status: StatusType = "OPEN"
class PositionCreate(PositionBase):
    """Pydantic model for creating a position"""
    status: StatusType = "OPEN"
    total_quantity: float = 0
    average_entry_price: Optional[float] = None
    realized_pnl: float = 0
    unrealized_pnl: float = 0
    max_trade_limit: float = 0

class PositionUpdate(BaseModel):
    """Pydantic model for updating a position"""
    symbol: Optional[str] = None
    strategy: Optional[str] = None
    status: Optional[StatusType] = None
    total_quantity: Optional[float] = None
    average_entry_price: Optional[float] = None
    realized_pnl: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    close_time: Optional[datetime] = None

class PositionInDB(PositionBase):
    """Pydantic model for position in database"""
    id: int
    total_quantity: float
    average_entry_price: Optional[float] = None
    realized_pnl: float
    unrealized_pnl: float
    status: StatusType
    open_time: datetime
    close_time: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

# SQLAlchemy ORM model
class Position(Base):
    """SQLAlchemy ORM model for Position"""
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    strategy = Column(String, default="TIME_BASED_STRADDLE")
    status = Column(String, default="OPEN")
    total_quantity = Column(Float)
    average_entry_price = Column(Float, nullable=True)
    realized_pnl = Column(Float, default=0)
    unrealized_pnl = Column(Float, default=0)
    open_time = Column(DateTime, default=datetime.utcnow)
    close_time = Column(DateTime, nullable=True)
    max_trade_limit = Column(Float, default=0)
