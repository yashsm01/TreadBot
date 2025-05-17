from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class UserPortfolioSummary(Base):
    """
    Model for tracking user portfolio summary metrics over time
    Updated after each straddle operation runs
    """
    __tablename__ = "user_portfolio_summary"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("telegram_users.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Total portfolio value
    total_value = Column(Float, nullable=False, default=0.0)
    total_cost_basis = Column(Float, nullable=False, default=0.0)
    total_profit_loss = Column(Float, nullable=False, default=0.0)
    total_profit_loss_percentage = Column(Float, nullable=False, default=0.0)

    # Asset distribution
    crypto_value = Column(Float, nullable=False, default=0.0)
    stable_value = Column(Float, nullable=False, default=0.0)

    # Performance metrics
    daily_change = Column(Float, nullable=True)
    weekly_change = Column(Float, nullable=True)
    monthly_change = Column(Float, nullable=True)

    # Store details of each asset in portfolio
    assets = Column(JSON, nullable=True)  # JSON field to store all assets with their details

    # Trading metrics
    trades_today = Column(Integer, default=0)
    swaps_today = Column(Integer, default=0)
    realized_profit_today = Column(Float, default=0.0)

    # Market conditions at time of snapshot
    market_trend = Column(String(10), nullable=True)  # up, down, sideways
    market_volatility = Column(Float, nullable=True)

    # Strategy indicators
    is_hedged = Column(Boolean, default=False)
    risk_level = Column(Integer, default=2)  # 1-5 scale, lower is safer

    # Relationship
    user = relationship("TelegramUser", back_populates="portfolio_summaries")

    def __repr__(self):
        return f"<UserPortfolioSummary(id={self.id}, user_id={self.user_id}, timestamp={self.timestamp}, total_value={self.total_value})>"
