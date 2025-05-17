from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime

class TelegramUser(Base):
    __tablename__ = "telegram_users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    chat_id = Column(String, unique=True, nullable=False)
    username = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_interaction = Column(DateTime, default=datetime.utcnow)

    # Add relationship to portfolio summaries
    portfolio_summaries = relationship("UserPortfolioSummary", back_populates="user")

class TelegramNotification(Base):
    __tablename__ = "telegram_notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("telegram_users.telegram_id"), nullable=False)
    message_type = Column(String, nullable=False)  # TRADE, ALERT, STRADDLE, SYSTEM
    symbol = Column(String)
    content = Column(String, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
    is_sent = Column(Boolean, default=False)
    error_message = Column(String)

    # Relationship
    user = relationship("TelegramUser")
