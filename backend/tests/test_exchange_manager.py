import pytest
import logging
from backend.trader.exchange_manager import ExchangeManager
from backend.database import get_db, Base, engine
from sqlalchemy.orm import Session
from backend.services.crypto_service import CryptoService

logger = logging.getLogger(__name__)

@pytest.fixture(scope="function")
def db():
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
async def exchange_manager(db: Session):
    """Create an exchange manager instance and sync cryptocurrencies"""
    manager = ExchangeManager(db)
    # Sync cryptocurrencies to have test data
    await manager.crypto_service.sync_cryptocurrencies()
    return manager

@pytest.mark.asyncio
async def test_initialization(exchange_manager):
    """Test exchange manager initialization"""
    assert exchange_manager is not None
    assert exchange_manager.exchange is not None
    assert exchange_manager.crypto_service is not None

@pytest.mark.asyncio
async def test_get_all_active_pairs(exchange_manager):
    """Test getting all active trading pairs"""
    pairs = exchange_manager.get_all_active_pairs()
    assert isinstance(pairs, list)
    assert len(pairs) > 0  # Should have some pairs after sync
    assert "BTC/USDT" in pairs  # Common trading pair should be present

@pytest.mark.asyncio
async def test_validate_trading_pair(exchange_manager):
    """Test trading pair validation"""
    # Test with a valid pair
    is_valid = await exchange_manager.validate_trading_pair("BTC/USDT")
    assert isinstance(is_valid, bool)
    assert is_valid  # BTC/USDT should be valid

    # Test with an invalid pair
    is_valid = await exchange_manager.validate_trading_pair("INVALID/PAIR")
    assert not is_valid

@pytest.mark.asyncio
async def test_get_ticker(exchange_manager):
    """Test getting ticker information"""
    # Test with a valid pair
    ticker = await exchange_manager.get_ticker("BTC/USDT")
    assert ticker is not None  # Should get ticker after sync
    assert isinstance(ticker, dict)
    assert 'symbol' in ticker
    assert 'last' in ticker
    assert 'bid' in ticker
    assert 'ask' in ticker
    assert 'volume' in ticker
    assert 'timestamp' in ticker

    # Test with an invalid pair
    ticker = await exchange_manager.get_ticker("INVALID/PAIR")
    assert ticker is None

@pytest.mark.asyncio
async def test_get_ohlcv(exchange_manager):
    """Test getting OHLCV data"""
    # Test with a valid pair
    ohlcv = await exchange_manager.get_ohlcv("BTC/USDT", timeframe='1h', limit=10)
    assert ohlcv is not None  # Should get OHLCV data after sync
    assert isinstance(ohlcv, list)
    assert len(ohlcv) <= 10  # Should not exceed the limit
    if len(ohlcv) > 0:
        # Each OHLCV entry should have [timestamp, open, high, low, close, volume]
        assert len(ohlcv[0]) == 6

    # Test with an invalid pair
    ohlcv = await exchange_manager.get_ohlcv("INVALID/PAIR")
    assert ohlcv is None

    # Test with different timeframes
    timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
    for timeframe in timeframes:
        ohlcv = await exchange_manager.get_ohlcv("BTC/USDT", timeframe=timeframe, limit=5)
        assert ohlcv is not None
        assert isinstance(ohlcv, list)
        assert len(ohlcv) <= 5
