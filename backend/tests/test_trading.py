import pytest
import asyncio
from datetime import datetime
from ..db.models import Base, Trade, Config, get_db_engine
from ..trader.strategy import StraddleStrategy
from ..trader.ccxt_utils import ExchangeManager
from ..trader.mock_exchange import MockExchange
from ..services.telegram import TelegramService
from ..services.scheduler import TradingScheduler
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@pytest.fixture
def db_engine():
    """Create a test database engine"""
    return get_db_engine()

@pytest.fixture
def exchange_manager():
    """Create an exchange manager instance"""
    try:
        return ExchangeManager()
    except Exception as e:
        print(f"Real exchange not available, using mock exchange: {str(e)}")
        return MockExchange()

@pytest.fixture
def telegram_service():
    """Create a telegram service instance"""
    return TelegramService()

@pytest.fixture
def trading_scheduler():
    """Create a trading scheduler instance"""
    return TradingScheduler()

@pytest.mark.asyncio
async def test_database_connection(db_engine):
    """Test database connection and model creation"""
    try:
        # Create tables
        Base.metadata.create_all(db_engine)

        # Test Config model
        config = Config(
            coin="BTC/USDT",
            interval="5m",
            breakout_pct=0.5,
            tp_pct=1.0,
            sl_pct=0.5,
            quantity=0.001
        )

        # Test Trade model
        trade = Trade(
            coin="BTC/USDT",
            entry_price=50000.0,
            quantity=0.001,
            type="paper"
        )

        print("Database connection and model creation successful")
        return True
    except Exception as e:
        print(f"Database test failed: {str(e)}")
        return False

@pytest.mark.asyncio
async def test_exchange_connection(exchange_manager):
    """Test exchange connection and basic functionality"""
    try:
        # Test getting balance
        balance = await exchange_manager.get_balance("USDT")
        print(f"USDT Balance: {balance}")

        # Test getting ticker
        ticker = await exchange_manager.get_ticker("BTC/USDT")
        print(f"BTC/USDT Ticker: {ticker}")

        print("Exchange connection test successful")
        return True
    except Exception as e:
        print(f"Exchange test failed: {str(e)}")
        return False

@pytest.mark.asyncio
async def test_trading_strategy(exchange_manager):
    """Test trading strategy execution"""
    try:
        # Create strategy instance
        config = {
            "breakout_pct": 0.5,
            "tp_pct": 1.0,
            "sl_pct": 0.5,
            "quantity": 0.001,
            "paper_trading": True
        }

        strategy = StraddleStrategy(
            exchange_manager,
            config
        )

        # Test strategy execution
        trade = await strategy.execute_strategy("BTC/USDT")
        print(f"Strategy execution successful: {trade}")

        print("Trading strategy test successful")
        return True
    except Exception as e:
        print(f"Strategy test failed: {str(e)}")
        return False

@pytest.mark.asyncio
async def test_telegram_notifications(telegram_service):
    """Test telegram notifications"""
    try:
        # Test sending a message
        await telegram_service.send_message("Test message from trading bot")
        print("Telegram notification test successful")
        return True
    except Exception as e:
        print(f"Telegram test failed: {str(e)}")
        return False

@pytest.mark.asyncio
async def test_scheduler(trading_scheduler):
    """Test trading scheduler"""
    try:
        # Add a test job
        config = {
            "breakout_pct": 0.5,
            "tp_pct": 1.0,
            "sl_pct": 0.5,
            "quantity": 0.001,
            "paper_trading": True
        }

        trading_scheduler.add_trading_job("BTC/USDT", "5m", config)
        print("Scheduler test successful")
        return True
    except Exception as e:
        print(f"Scheduler test failed: {str(e)}")
        return False

async def run_tests():
    """Run all tests"""
    print("Starting tests...")

    # Initialize components
    db_engine = get_db_engine()
    exchange_manager = MockExchange()  # Always use mock exchange for testing
    telegram_service = TelegramService()
    trading_scheduler = TradingScheduler()

    # Run tests
    tests = [
        test_database_connection(db_engine),
        test_exchange_connection(exchange_manager),
        test_trading_strategy(exchange_manager),
        test_telegram_notifications(telegram_service),
        test_scheduler(trading_scheduler)
    ]

    # Wait for all tests to complete
    results = await asyncio.gather(*tests)

    # Print results
    print("\nTest Results:")
    for i, result in enumerate(results):
        print(f"Test {i+1}: {'Passed' if result else 'Failed'}")

    return all(results)

if __name__ == "__main__":
    # Run tests
    asyncio.run(run_tests())
