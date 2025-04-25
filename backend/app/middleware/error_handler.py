from fastapi import Request, status
from fastapi.responses import JSONResponse
from app.core.logger import logger
from app.services.telegram_service import telegram_service

async def error_handler(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        # Log the error
        logger.error(f"Unhandled error: {str(e)}")

        # Send error notification via Telegram
        await telegram_service.notify_error(
            f"Unhandled error in {request.url.path}: {str(e)}"
        )

        # Return error response
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error. The error has been logged and reported."
            }
        )
