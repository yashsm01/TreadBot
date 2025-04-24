from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Optional
from pydantic import BaseModel
from ..database import get_db
from ..services.telegram import TelegramService
from ..services.portfolio import PortfolioService
import logging

router = APIRouter(prefix="/debug/telegram", tags=["telegram-debug"])
logger = logging.getLogger(__name__)

class TelegramResponse(BaseModel):
    success: bool
    message: str

class TelegramNotificationResponse(BaseModel):
    success: bool
    notification_type: str
    message: str

class TelegramStatusResponse(BaseModel):
    initialized: bool
    has_bot: bool
    has_chat_id: bool

class TelegramCommandResponse(BaseModel):
    command: str
    args: Optional[str]
    valid: bool
    message: str

async def get_telegram_service() -> TelegramService:
    """Dependency to get telegram service instance"""
    from ..main import telegram_service
    return telegram_service

@router.post("/send-message", response_model=TelegramResponse)
async def debug_send_message(
    message: str = Query(..., description="Message to send"),
    telegram_service: TelegramService = Depends(get_telegram_service),
) -> Dict:
    """Debug endpoint for sending basic messages"""
    try:
        success = await telegram_service.send_message(message)
        return {
            "success": success,
            "message": "Message sent successfully" if success else "Failed to send message"
        }
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/notification/{notification_type}", response_model=TelegramNotificationResponse)
async def debug_notification(
    notification_type: str,
    telegram_service: TelegramService = Depends(get_telegram_service),
) -> Dict:
    """Debug endpoint for testing different notification types"""
    try:
        result = False
        if notification_type == "error":
            result = await telegram_service.send_error_notification(
                "Debug error message",
                {"type": "debug", "details": "Test error notification"}
            )
        elif notification_type == "trade":
            result = await telegram_service.send_trade_notification(
                "Debug Strategy",
                "BTC/USDT",
                50000.0,
                0.1
            )
        elif notification_type == "test":
            result = await telegram_service.send_test_notification()
        else:
            raise HTTPException(status_code=400, detail="Invalid notification type")

        return {
            "success": result,
            "notification_type": notification_type,
            "message": "Notification sent successfully" if result else "Failed to send notification"
        }
    except Exception as e:
        logger.error(f"Error sending {notification_type} notification: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status", response_model=TelegramStatusResponse)
async def debug_status(
    telegram_service: TelegramService = Depends(get_telegram_service),
) -> Dict:
    """Debug endpoint for checking Telegram service status"""
    return {
        "initialized": telegram_service._initialized,
        "has_bot": bool(telegram_service.bot),
        "has_chat_id": bool(telegram_service.chat_id)
    }

@router.post("/command", response_model=TelegramCommandResponse)
async def debug_command(
    command: str = Query(..., description="Command to test"),
    args: Optional[str] = Query(None, description="Command arguments"),
    telegram_service: TelegramService = Depends(get_telegram_service),
) -> Dict:
    """Debug endpoint for testing command handling"""
    try:
        # Create mock command context
        command_text = f"{command} {args}" if args else command
        logger.debug(f"Testing command: {command_text}")

        return {
            "command": command,
            "args": args,
            "valid": command in ["/start", "/help", "/status", "/portfolio", "/analysis"],
            "message": "Command structure is valid"
        }
    except Exception as e:
        logger.error(f"Error testing command: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
