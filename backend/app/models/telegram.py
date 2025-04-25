from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class TelegramUser(Base):
    __tablename__ = "telegram_users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    chat_id = Column(String, unique=True, nullable=False)
    username = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_interaction = Column(DateTime(timezone=True), onupdate=func.now())

class TelegramNotification(Base):
    __tablename__ = "telegram_notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("telegram_users.telegram_id"), nullable=False)
    message_type = Column(String, nullable=False)  # TRADE, ALERT, STRADDLE, SYSTEM
    symbol = Column(String)
    content = Column(String, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    is_sent = Column(Boolean, default=False)
    error_message = Column(String)

    # Relationship
    user = relationship("TelegramUser")
