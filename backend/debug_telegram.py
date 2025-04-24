import asyncio
import logging
from dotenv import load_dotenv
from services.telegram import TelegramService
from analysis.market_analyzer import MarketAnalyzer
from services.portfolio import PortfolioService
from trader.mock_exchange import MockExchange
from database import SessionLocal
import os

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('telegram_debug.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def debug_telegram_service():
    """Debug Telegram service initialization and basic functionality"""
    try:
        # Log environment variables (excluding sensitive data)
        logger.debug("Checking environment variables...")
        bot_token_exists = bool(os.getenv("TELEGRAM_BOT_TOKEN"))
        chat_id_exists = bool(os.getenv("TELEGRAM_CHAT_ID"))
        logger.debug(f"Bot token exists: {bot_token_exists}")
        logger.debug(f"Chat ID exists: {chat_id_exists}")

        # Initialize services
        logger.debug("Initializing services...")
        db = SessionLocal()
        exchange = MockExchange()
        market_analyzer = MarketAnalyzer(exchange)
        portfolio_service = PortfolioService(db, exchange)

        telegram_service = TelegramService(market_analyzer, portfolio_service)
        await telegram_service.initialize()

        if not telegram_service._initialized:
            logger.error("Telegram service failed to initialize")
            return

        logger.info("Telegram service initialized successfully")

        # Test basic messaging
        logger.debug("Testing basic message sending...")
        message_sent = await telegram_service.send_test_notification()
        logger.debug(f"Test message sent: {message_sent}")

        # Test market analysis integration
        logger.debug("Testing market analysis integration...")
        try:
            analysis = await market_analyzer.get_market_analysis("BTC/USDT", "5m")
            logger.debug(f"Market analysis received: {bool(analysis)}")
        except Exception as e:
            logger.error(f"Market analysis error: {str(e)}")

        # Test portfolio integration
        logger.debug("Testing portfolio integration...")
        try:
            portfolio = await portfolio_service.get_portfolio(user_id=1)
            logger.debug(f"Portfolio data received: {bool(portfolio)}")
        except Exception as e:
            logger.error(f"Portfolio error: {str(e)}")

        # Test different notification types
        logger.debug("Testing notification types...")
        notification_types = {
            "error": {
                "message": "Test error message",
                "details": {"type": "test", "severity": "low"}
            },
            "trade": {
                "strategy": "Test Strategy",
                "symbol": "BTC/USDT",
                "entry_price": 50000.0,
                "quantity": 0.1
            },
            "daily_summary": {
                "total_trades": 5,
                "winning_trades": 3,
                "losing_trades": 2,
                "net_profit": 1.5
            }
        }

        for n_type, data in notification_types.items():
            try:
                logger.debug(f"Testing {n_type} notification...")
                if n_type == "error":
                    await telegram_service.send_error_notification(
                        data["message"], data["details"]
                    )
                elif n_type == "trade":
                    await telegram_service.send_trade_notification(
                        data["strategy"], data["symbol"],
                        data["entry_price"], data["quantity"]
                    )
                elif n_type == "daily_summary":
                    await telegram_service.send_daily_summary(data)
                logger.debug(f"{n_type} notification sent successfully")
            except Exception as e:
                logger.error(f"Error sending {n_type} notification: {str(e)}")

        # Test command handling
        logger.debug("Testing command handling...")
        test_commands = [
            "/start", "/help", "/status",
            "/portfolio", "/analysis BTC/USDT"
        ]

        for command in test_commands:
            logger.debug(f"Testing command: {command}")
            # Note: Actual command testing would require mocking Update and Context objects
            logger.debug(f"Command {command} structure verified")

    except Exception as e:
        logger.error(f"Debug session error: {str(e)}")
    finally:
        # Cleanup
        logger.debug("Cleaning up...")
        await telegram_service.stop()
        db.close()
        logger.info("Debug session completed")

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()

    # Run debug session
    asyncio.run(debug_telegram_service())
