import asyncio
import platform
import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.services.market_analyzer import market_analyzer
from backend.app.core.logger import logger
from backend.app.core.exchange.exchange_manager import exchange_manager

async def test_market_analysis():
    """Test market analysis functionality"""
    try:
        analysis = await market_analyzer.get_market_analysis('BTCUSDT')
        print("Market Analysis Result:")
        print(analysis)
    except Exception as e:
        logger.error(f"Error in market analysis: {str(e)}")
        raise
    finally:
        # Close exchange connection
        await exchange_manager.close()

if __name__ == "__main__":
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_market_analysis())
