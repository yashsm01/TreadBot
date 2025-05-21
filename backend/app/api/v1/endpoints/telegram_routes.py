from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict
from app.core.database import get_db
from app.services.telegram_service import telegram_service

router = APIRouter()

@router.post("/webhook")
async def telegram_webhook(
    update_data: Dict,
    db: AsyncSession = Depends(get_db)
):
    """Handle Telegram webhook updates"""
    try:
        await telegram_service.application.process_update(update_data)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def telegram_status(
    db: AsyncSession = Depends(get_db)
):
    """Get Telegram bot status"""
    try:
        return {
            "status": "active" if telegram_service._initialized else "inactive",
            "webhook_info": await telegram_service.get_webhook_info()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
