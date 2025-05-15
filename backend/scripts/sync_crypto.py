import asyncio
import sys
import os
import platform

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.services.crypto_service import CryptoService
from app.core.logger import logger

async def sync_cryptocurrencies():
    """Sync cryptocurrency data from Binance exchange"""
    db = SessionLocal()
    try:
        crypto_service = CryptoService(db)
        await crypto_service.sync_cryptocurrencies()
        logger.info("Successfully synchronized cryptocurrency data")
    except Exception as e:
        logger.error(f"Error syncing cryptocurrency data: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(sync_cryptocurrencies())
