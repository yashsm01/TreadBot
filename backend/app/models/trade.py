from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from ..core.database import Base

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    side = Column(String)  # "BUY" or "SELL"
    quantity = Column(Float)
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    entry_time = Column(DateTime, default=datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)
    pnl = Column(Float, nullable=True)
    status = Column(String)  # "OPEN" or "CLOSED"
    position_id = Column(Integer, ForeignKey("positions.id"))

    position = relationship("Position", back_populates="trades")

    def close_trade(self, exit_price: float):
        """Close a trade and calculate PnL"""
        if self.status == "CLOSED":
            raise ValueError("Trade is already closed")

        self.exit_price = exit_price
        self.exit_time = datetime.utcnow()
        self.status = "CLOSED"

        # Calculate PnL
        if self.side == "BUY":
            self.pnl = (self.exit_price - self.entry_price) * self.quantity
        else:  # SELL
            self.pnl = (self.entry_price - self.exit_price) * self.quantity

        # Update position metrics
        if self.position:
            self.position.update_position_metrics()
