import asyncio
import logging
from telegram import Bot
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def test_telegram_commands():
    """Test all Telegram bot commands"""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        logger.error("Bot token or chat ID not set in environment variables")
        return

    bot = Bot(token=bot_token)

    # List of commands to test
    commands = [
        # Basic commands
        "/start",
        "/help",
        "/pairs",

        # Market information
        "/analysis BTC/USDT",
        "/analysis BTC/USDT 5m",
        "/signals BTC/USDT",
        "/signals BTC/USDT 1h",

        # Trading commands
        "/buy BTC/USDT 0.1 50000",
        "/sell BTC/USDT 0.05 51000",

        # Portfolio management
        "/portfolio",
        "/history",
        "/history BTC/USDT",
        "/profit daily",
        "/profit weekly",

        # Invalid commands for error testing
        "/analysis",  # Missing symbol
        "/buy BTC/USDT",  # Missing quantity and price
        "/sell",  # Missing all parameters
        "/profit invalid"  # Invalid timeframe
    ]

    try:
        # Send test notification
        await bot.send_message(
            chat_id=chat_id,
            text="🔄 Starting Telegram bot feature testing..."
        )

        # Test each command
        for command in commands:
            try:
                logger.info(f"Testing command: {command}")
                await bot.send_message(chat_id=chat_id, text=command)
                # Wait for bot to process command
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Error testing command {command}: {str(e)}")

        # Send completion message
        await bot.send_message(
            chat_id=chat_id,
            text="✅ Telegram bot feature testing completed!"
        )

    except Exception as e:
        logger.error(f"Error during testing: {str(e)}")
    finally:
        await bot.close()

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_telegram_commands())
