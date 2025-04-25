from typing import Optional, List
from sqlalchemy.orm import Session
from ..models.telegram import TelegramUser, TelegramNotification
from datetime import datetime

class CRUDTelegram:
    async def create_user(
        self,
        db: Session,
        telegram_id: int,
        chat_id: str,
        username: Optional[str] = None
    ) -> TelegramUser:
        """Create a new telegram user"""
        db_user = TelegramUser(
            telegram_id=telegram_id,
            chat_id=chat_id,
            username=username
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    async def get_user_by_telegram_id(
        self,
        db: Session,
        telegram_id: int
    ) -> Optional[TelegramUser]:
        """Get user by telegram ID"""
        return db.query(TelegramUser).filter(
            TelegramUser.telegram_id == telegram_id
        ).first()

    async def update_user_status(
        self,
        db: Session,
        telegram_id: int,
        is_active: bool
    ) -> Optional[TelegramUser]:
        """Update user active status"""
        db_user = await self.get_user_by_telegram_id(db, telegram_id)
        if db_user:
            db_user.is_active = is_active
            db_user.last_interaction = datetime.utcnow()
            db.commit()
            db.refresh(db_user)
        return db_user

    async def create_notification(
        self,
        db: Session,
        user_id: int,
        message_type: str,
        content: str,
        symbol: Optional[str] = None
    ) -> TelegramNotification:
        """Create a new notification"""
        db_notification = TelegramNotification(
            user_id=user_id,
            message_type=message_type,
            content=content,
            symbol=symbol
        )
        db.add(db_notification)
        db.commit()
        db.refresh(db_notification)
        return db_notification

    async def mark_notification_sent(
        self,
        db: Session,
        notification_id: int
    ) -> Optional[TelegramNotification]:
        """Mark notification as sent"""
        db_notification = db.query(TelegramNotification).get(notification_id)
        if db_notification:
            db_notification.is_sent = True
            db.commit()
            db.refresh(db_notification)
        return db_notification

    async def update_notification_error(
        self,
        db: Session,
        notification_id: int,
        error_message: str
    ) -> Optional[TelegramNotification]:
        """Update notification with error message"""
        db_notification = db.query(TelegramNotification).get(notification_id)
        if db_notification:
            db_notification.error_message = error_message
            db.commit()
            db.refresh(db_notification)
        return db_notification

    async def get_user_notifications(
        self,
        db: Session,
        user_id: int,
        limit: int = 50
    ) -> List[TelegramNotification]:
        """Get user's notifications"""
        return db.query(TelegramNotification).filter(
            TelegramNotification.user_id == user_id
        ).order_by(
            TelegramNotification.sent_at.desc()
        ).limit(limit).all()

telegram_crud = CRUDTelegram()
