from sqlalchemy import Column, Integer, Float, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from ..core.database import Base

class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    strategy = Column(String, index=True)  # e.g., "TIME_BASED_STRADDLE"
    total_quantity = Column(Float, default=0)
    average_entry_price = Column(Float, nullable=True)
    realized_pnl = Column(Float, default=0)
    unrealized_pnl = Column(Float, default=0)
    status = Column(String)  # "ACTIVE" or "CLOSED"
    open_time = Column(DateTime, default=datetime.utcnow)
    close_time = Column(DateTime, nullable=True)

    trades = relationship("Trade", back_populates="position")

    def update_position_metrics(self):
        """Update position metrics based on associated trades"""
        total_value = 0
        self.total_quantity = 0
        self.realized_pnl = 0

        for trade in self.trades:
            if trade.status == "OPEN":
                if trade.side == "BUY":
                    self.total_quantity += trade.quantity
                else:
                    self.total_quantity -= trade.quantity
                total_value += trade.entry_price * trade.quantity
            elif trade.status == "CLOSED":
                self.realized_pnl += trade.pnl

        if self.total_quantity != 0:
            self.average_entry_price = total_value / abs(self.total_quantity)
            self.status = "ACTIVE"
        else:
            self.average_entry_price = None
            self.status = "CLOSED"
            self.close_time = datetime.utcnow()
