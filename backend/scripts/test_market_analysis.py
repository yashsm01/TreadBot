import asyncio
import platform
import sys
import os
import json
from datetime import datetime

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.market_analyzer import market_analyzer
from app.core.logger import logger
from app.core.exchange.exchange_manager import exchange_manager

def format_response(response: dict) -> str:
    """Format the response for better readability"""
    if response.get('error'):
        return f"""
Error in Market Analysis:
------------------------
Symbol: {response.get('symbol')}
Error Message: {response.get('message')}
Error Type: {response.get('error_type', 'unknown')}
"""
    else:
        return f"""
Market Analysis Result:
----------------------
Symbol: {response.get('symbol')}
Current Price: {response.get('current_price')}
Bid/Ask: {response.get('bid')}/{response.get('ask')}
24h Volume: {response.get('volume_24h')}
Volatility: {response.get('volatility')}
Trading Signal: {json.dumps(response.get('trading_signal', {}), indent=2)}
Market Conditions: {json.dumps(response.get('market_conditions', {}), indent=2)}
Timestamp: {response.get('timestamp')}
"""

async def test_market_analysis():
    """Test market analysis functionality"""
    try:
        # Test with different symbol formats
        symbols = ['BTCUSDT', 'BTC/USDT', 'ETHUSDT', 'ETH/USDT']

        for symbol in symbols:
            print(f"\nTesting market analysis for {symbol}...")
            analysis = await market_analyzer.get_market_analysis(symbol)
            print(format_response(analysis))

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
