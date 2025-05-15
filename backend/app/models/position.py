from sqlalchemy import Column, Integer, Float, String, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime


class Position(Base):
    """SQLAlchemy ORM model for Position"""
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    strategy = Column(String, default="TIME_BASED_STRADDLE")
    status = Column(String, default="OPEN")
    total_quantity = Column(Float, default=0)
    average_entry_price = Column(Float, nullable=True)
    realized_pnl = Column(Float, default=0)
    unrealized_pnl = Column(Float, default=0)
    open_time = Column(DateTime, default=datetime.utcnow)
    close_time = Column(DateTime, nullable=True)

    # Define the relationship with trades - back reference
    trades = relationship("Trade", back_populates="position")

    def update_position_metrics(self):
        """Update position metrics based on associated trades"""
        if not self.trades:
            return

        # Calculate totals from trades
        self.realized_pnl = sum(trade.realized_pnl or 0 for trade in self.trades
                              if trade.status == "CLOSED")
        self.unrealized_pnl = sum(trade.unrealized_pnl or 0 for trade in self.trades
                                if trade.status == "OPEN")

        # If all trades are closed, mark position as closed
        if all(trade.status in ["CLOSED", "CANCELLED"] for trade in self.trades):
            self.status = "CLOSED"
            self.close_time = datetime.utcnow()
