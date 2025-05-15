from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.telegram import TelegramUser, TelegramNotification
from app.crud.base import CRUDBase

class CRUDTelegramUser(CRUDBase[TelegramUser, dict, dict]):
    async def get_by_telegram_id(self, db: AsyncSession, telegram_id: int) -> Optional[TelegramUser]:
        """Get user by Telegram ID"""
        stmt = select(TelegramUser).where(TelegramUser.telegram_id == telegram_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_users(self, db: AsyncSession) -> List[TelegramUser]:
        """Get all active users"""
        stmt = select(TelegramUser).where(TelegramUser.is_active == True)
        result = await db.execute(stmt)
        return list(result.scalars().all())

class CRUDTelegramNotification(CRUDBase[TelegramNotification, dict, dict]):
    async def get_pending_notifications(self, db: AsyncSession) -> List[TelegramNotification]:
        """Get all unsent notifications"""
        stmt = select(TelegramNotification).where(TelegramNotification.is_sent == False)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def mark_as_sent(self, db: AsyncSession, notification_id: int) -> Optional[TelegramNotification]:
        """Mark notification as sent"""
        stmt = select(TelegramNotification).where(TelegramNotification.id == notification_id)
        result = await db.execute(stmt)
        notification = result.scalar_one_or_none()
        if notification:
            notification.is_sent = True
            db.add(notification)
            await db.commit()
        return notification

    async def get_user_notifications(
        self,
        db: AsyncSession,
        user_id: int,
        limit: int = 100
    ) -> List[TelegramNotification]:
        """Get notifications for a specific user"""
        stmt = (
            select(TelegramNotification)
            .where(TelegramNotification.user_id == user_id)
            .order_by(TelegramNotification.sent_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

# Create instances
telegram_user = CRUDTelegramUser(TelegramUser)
telegram_notification = CRUDTelegramNotification(TelegramNotification)
