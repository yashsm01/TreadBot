from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.core.database import Base
# Import Position here if you need to use it directly,
# otherwise SQLAlchemy can handle the string reference

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    side = Column(String)  # "BUY" or "SELL"
    quantity = Column(Float)
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    order_type = Column(String, default="STOP")  # "MARKET", "LIMIT", "STOP"
    strategy = Column(String, default="STRADDLE")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    entered_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    # Trade metrics
    pnl = Column(Float, nullable=True)
    realized_pnl = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, nullable=True)
    status = Column(String)  # "PENDING", "OPEN", "CLOSED", "CANCELLED"
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=True)
    current_price = Column(Float, nullable=True)

    position = relationship("Position", back_populates="trades")

    def close_trade(self, exit_price: float):
        """Close a trade and calculate PnL"""
        if self.status == "CLOSED":
            raise ValueError("Trade is already closed")

        self.exit_price = exit_price
        self.closed_at = datetime.utcnow()
        self.status = "CLOSED"

        # Calculate PnL
        if self.side == "BUY":
            self.realized_pnl = (self.exit_price - self.entry_price) * self.quantity
        else:  # SELL
            self.realized_pnl = (self.entry_price - self.exit_price) * self.quantity

        self.pnl = self.realized_pnl

        # Update position metrics
        if self.position:
            self.position.update_position_metrics()

    def update_unrealized_pnl(self, current_price: float):
        """Update unrealized PnL based on current market price"""
        if self.status != "OPEN":
            return

        if self.side == "BUY":
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
        else:  # SELL
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity
