from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    symbol = Column(String, nullable=False)
    quantity = Column(Float, default=0, nullable=False)
    avg_buy_price = Column(Float, nullable=False, default=0.0)
    realized_profit = Column(Float, default=0.0, nullable=False)  # Cumulative realized P/L
    last_updated = Column(DateTime, default=datetime.utcnow)
    asset_type = Column(String, nullable=True)
    current_price = Column(Float, nullable=False, default=0.0)

    # Relationships
    transactions = relationship("Transaction", back_populates="portfolio")

    def update_price(self, new_price: float):
        self.current_price = new_price
        self.last_updated = datetime.utcnow()
