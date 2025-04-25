from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...core.database import get_db
from ...crud.crud_telegram import telegram_crud
from ...services.telegram_service import telegram_service

router = APIRouter()

@router.post("/webhook")
async def telegram_webhook(update_data: Dict, db: Session = Depends(get_db)):
    """Handle Telegram webhook updates"""
    try:
        # Process the update
        await telegram_service.application.process_update(update_data)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/notifications/{user_id}")
async def get_user_notifications(
    user_id: int,
    limit: int = 50,
    db: Session = Depends(get_db)
) -> List[Dict]:
    """Get notifications for a user"""
    try:
        notifications = await telegram_crud.get_user_notifications(db, user_id, limit)
        return [
            {
                "id": n.id,
                "message_type": n.message_type,
                "content": n.content,
                "symbol": n.symbol,
                "sent_at": n.sent_at.isoformat(),
                "is_sent": n.is_sent,
                "error_message": n.error_message
            }
            for n in notifications
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/users")
async def create_telegram_user(
    telegram_id: int,
    chat_id: str,
    username: str = None,
    db: Session = Depends(get_db)
):
    """Create a new Telegram user"""
    try:
        user = await telegram_crud.create_user(
            db=db,
            telegram_id=telegram_id,
            chat_id=chat_id,
            username=username
        )
        return {
            "telegram_id": user.telegram_id,
            "chat_id": user.chat_id,
            "username": user.username,
            "is_active": user.is_active
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/users/{telegram_id}/status")
async def update_user_status(
    telegram_id: int,
    is_active: bool,
    db: Session = Depends(get_db)
):
    """Update user's active status"""
    try:
        user = await telegram_crud.update_user_status(
            db=db,
            telegram_id=telegram_id,
            is_active=is_active
        )
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "telegram_id": user.telegram_id,
            "is_active": user.is_active
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
