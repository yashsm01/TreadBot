from typing import Optional, List
from sqlalchemy.orm import Session
from ..models.telegram import TelegramUser, TelegramNotification
from .base import CRUDBase

class CRUDTelegramUser(CRUDBase[TelegramUser, dict, dict]):
    def get_by_telegram_id(self, db: Session, telegram_id: int) -> Optional[TelegramUser]:
        """Get user by Telegram ID"""
        return db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).first()

    def get_active_users(self, db: Session) -> List[TelegramUser]:
        """Get all active users"""
        return db.query(TelegramUser).filter(TelegramUser.is_active == True).all()

class CRUDTelegramNotification(CRUDBase[TelegramNotification, dict, dict]):
    def get_pending_notifications(self, db: Session) -> List[TelegramNotification]:
        """Get all unsent notifications"""
        return db.query(TelegramNotification).filter(TelegramNotification.is_sent == False).all()

    def mark_as_sent(self, db: Session, notification_id: int) -> TelegramNotification:
        """Mark notification as sent"""
        notification = db.query(TelegramNotification).filter(TelegramNotification.id == notification_id).first()
        if notification:
            notification.is_sent = True
            db.commit()
        return notification

    def get_user_notifications(
        self,
        db: Session,
        user_id: int,
        limit: int = 100
    ) -> List[TelegramNotification]:
        """Get notifications for a specific user"""
        return (
            db.query(TelegramNotification)
            .filter(TelegramNotification.user_id == user_id)
            .order_by(TelegramNotification.sent_at.desc())
            .limit(limit)
            .all()
        )

# Create instances
telegram_user = CRUDTelegramUser(TelegramUser)
telegram_notification = CRUDTelegramNotification(TelegramNotification)
