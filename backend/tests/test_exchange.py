import pytest
import asyncio
from ..trader.exchange_manager import ExchangeManager
from ..trader.mock_exchange import MockExchange
from ..database import SessionLocal
from decimal import Decimal

@pytest.fixture
def exchange():
    """Create a mock exchange instance"""
    return MockExchange()

@pytest.fixture
def exchange_manager(db_session):
    """Create an exchange manager instance with mock exchange"""
    manager = ExchangeManager(db_session)
    return manager

@pytest.mark.asyncio
async def test_initialization(exchange_manager):
    """Test exchange manager initialization"""
    await exchange_manager.initialize()
    assert exchange_manager.exchange is not None
    assert exchange_manager.initialized is True

@pytest.mark.asyncio
async def test_get_ticker(exchange_manager):
    """Test getting ticker information"""
    await exchange_manager.initialize()
    ticker = await exchange_manager.get_ticker("BTC/USDT")

    assert ticker is not None
    assert "last" in ticker
    assert "bid" in ticker
    assert "ask" in ticker
    assert "volume" in ticker
    assert "timestamp" in ticker

@pytest.mark.asyncio
async def test_get_ohlcv(exchange_manager):
    """Test getting OHLCV data"""
    await exchange_manager.initialize()
    ohlcv = await exchange_manager.get_ohlcv("BTC/USDT", "5m", limit=100)

    assert len(ohlcv) > 0
    for candle in ohlcv:
        assert len(candle) == 6  # timestamp, open, high, low, close, volume
        assert all(isinstance(x, (int, float)) for x in candle[1:])

@pytest.mark.asyncio
async def test_create_order(exchange_manager):
    """Test order creation"""
    await exchange_manager.initialize()
    order = await exchange_manager.create_order(
        symbol="BTC/USDT",
        order_type="limit",
        side="buy",
        amount=0.1,
        price=50000.0
    )

    assert order is not None
    assert order["symbol"] == "BTC/USDT"
    assert order["type"] == "limit"
    assert order["side"] == "buy"
    assert float(order["amount"]) == 0.1
    assert float(order["price"]) == 50000.0

@pytest.mark.asyncio
async def test_get_order(exchange_manager):
    """Test getting order information"""
    await exchange_manager.initialize()
    # Create an order first
    order = await exchange_manager.create_order(
        symbol="BTC/USDT",
        order_type="limit",
        side="buy",
        amount=0.1,
        price=50000.0
    )

    # Get the order
    fetched_order = await exchange_manager.get_order(order["id"], "BTC/USDT")
    assert fetched_order is not None
    assert fetched_order["id"] == order["id"]
    assert fetched_order["symbol"] == order["symbol"]

@pytest.mark.asyncio
async def test_cancel_order(exchange_manager):
    """Test order cancellation"""
    await exchange_manager.initialize()
    # Create an order first
    order = await exchange_manager.create_order(
        symbol="BTC/USDT",
        order_type="limit",
        side="buy",
        amount=0.1,
        price=50000.0
    )

    # Cancel the order
    result = await exchange_manager.cancel_order(order["id"], "BTC/USDT")
    assert result is not None
    assert result["id"] == order["id"]
    assert result["status"] == "canceled"

@pytest.mark.asyncio
async def test_get_balance(exchange_manager):
    """Test getting account balance"""
    await exchange_manager.initialize()
    balance = await exchange_manager.get_balance()

    assert balance is not None
    assert "total" in balance
    assert "free" in balance
    assert "used" in balance

@pytest.mark.asyncio
async def test_validate_pair(exchange_manager):
    """Test trading pair validation"""
    await exchange_manager.initialize()
    # Test valid pair
    assert await exchange_manager.validate_pair("BTC/USDT") is True

    # Test invalid pair
    assert await exchange_manager.validate_pair("INVALID/PAIR") is False

@pytest.mark.asyncio
async def test_get_min_order_amount(exchange_manager):
    """Test getting minimum order amount"""
    await exchange_manager.initialize()
    min_amount = await exchange_manager.get_min_order_amount("BTC/USDT")

    assert min_amount is not None
    assert isinstance(min_amount, (int, float, Decimal))
    assert min_amount > 0

@pytest.mark.asyncio
async def test_error_handling(exchange_manager):
    """Test error handling"""
    await exchange_manager.initialize()

    # Test invalid symbol
    with pytest.raises(Exception):
        await exchange_manager.get_ticker("INVALID/PAIR")

    # Test invalid order type
    with pytest.raises(Exception):
        await exchange_manager.create_order(
            symbol="BTC/USDT",
            order_type="invalid",
            side="buy",
            amount=0.1,
            price=50000.0
        )

    # Test invalid order ID
    with pytest.raises(Exception):
        await exchange_manager.get_order("invalid_id", "BTC/USDT")

if __name__ == "__main__":
    pytest.main(["-v", __file__])
