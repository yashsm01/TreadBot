import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from ..main import app
from ..services.telegram import TelegramService
from ..database import SessionLocal
from datetime import datetime
from ..trader.mock_exchange import MockExchange

# Test client setup
client = TestClient(app)

@pytest.fixture
def db():
    """Create a test database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def mock_exchange():
    """Create a mock exchange"""
    exchange = MagicMock()
    # fetch_ticker is a synchronous method in CCXT
    exchange.fetch_ticker = MagicMock(return_value={
        'symbol': 'BTC/USDT',
        'last': 50000.0,
        'bid': 49900.0,
        'ask': 50100.0,
        'volume': 1000.0,
        'timestamp': datetime.now().timestamp() * 1000
    })
    # These methods are async in CCXT
    exchange.create_market_buy_order = AsyncMock(return_value={
        'id': '123456',
        'symbol': 'BTC/USDT',
        'type': 'market',
        'side': 'buy',
        'price': 50000.0,
        'amount': 0.1,
        'cost': 5000.0,
        'timestamp': datetime.now().timestamp() * 1000
    })
    exchange.create_market_sell_order = AsyncMock(return_value={
        'id': '123457',
        'symbol': 'BTC/USDT',
        'type': 'market',
        'side': 'sell',
        'price': 50000.0,
        'amount': 0.1,
        'cost': 5000.0,
        'timestamp': datetime.now().timestamp() * 1000
    })
    exchange.fetch_balance = AsyncMock(return_value={
        'BTC': {'free': 1.0, 'used': 0.0, 'total': 1.0},
        'USDT': {'free': 50000.0, 'used': 0.0, 'total': 50000.0}
    })
    exchange.has = {
        'fetchTickers': True,
        'fetchTicker': True
    }
    exchange.load_markets = MagicMock()
    exchange.market = MagicMock(return_value={'symbol': 'BTC/USDT'})
    return exchange

@pytest.fixture
def mock_telegram_service():
    """Create a mock telegram service"""
    with patch('backend.main.telegram_service') as mock_service:
        # Mock all the notification methods
        mock_service.send_test_notification = AsyncMock(return_value=True)
        mock_service.send_error_notification = AsyncMock(return_value=True)
        mock_service.send_trade_notification = AsyncMock(return_value=True)
        mock_service.send_daily_summary = AsyncMock(return_value=True)
        mock_service.bot = True  # Mock bot existence
        mock_service.chat_id = "123456789"  # Mock chat ID
        yield mock_service

@pytest.mark.asyncio
async def test_telegram_test_notification(mock_telegram_service, db):
    """Test the test notification endpoint"""
    response = client.post("/test/telegram?notification_type=test")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["message"] == "Successfully sent test notification"
    assert "timestamp" in data
    mock_telegram_service.send_test_notification.assert_called_once()

@pytest.mark.asyncio
async def test_telegram_error_notification(mock_telegram_service, db):
    """Test the error notification endpoint"""
    response = client.post("/test/telegram?notification_type=error")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["message"] == "Successfully sent error notification"
    assert "timestamp" in data
    mock_telegram_service.send_error_notification.assert_called_once_with(
        "Test error message",
        {
            "Error Type": "Test Error",
            "Component": "Test Component",
            "Additional Info": "This is a test error notification"
        }
    )

@pytest.mark.asyncio
async def test_telegram_trade_notification(mock_telegram_service, mock_exchange, db):
    """Test the trade notification endpoint"""
    # Mock the exchange manager and trading API
    with patch('backend.main.exchange_manager', mock_exchange), \
         patch('backend.api.trading.TradingAPI.manual_trade') as mock_trade:
        mock_trade.return_value = AsyncMock()
        response = client.post("/test/telegram?notification_type=trade")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["message"] == "Successfully sent trade notification"
        assert "timestamp" in data

@pytest.mark.asyncio
async def test_telegram_summary_notification(mock_telegram_service, db):
    """Test the summary notification endpoint"""
    response = client.post("/test/telegram?notification_type=summary")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["message"] == "Successfully sent summary notification"
    assert "timestamp" in data
    mock_telegram_service.send_daily_summary.assert_called_once_with({
        "total_trades": 10,
        "winning_trades": 6,
        "losing_trades": 4,
        "net_profit": 2.5,
        "best_trade": 1.5,
        "worst_trade": -0.8,
        "trades": [
            {
                "symbol": "BTC/USDT",
                "profit_pct": 1.5,
                "entry_price": 50000.0,
                "exit_price": 50750.0
            },
            {
                "symbol": "ETH/USDT",
                "profit_pct": -0.8,
                "entry_price": 3000.0,
                "exit_price": 2976.0
            }
        ]
    })

@pytest.mark.asyncio
async def test_telegram_invalid_notification_type(mock_telegram_service, db):
    """Test invalid notification type"""
    response = client.post("/test/telegram?notification_type=invalid")
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "Invalid notification type" in data["detail"]

@pytest.mark.asyncio
async def test_telegram_missing_notification_type(mock_telegram_service, db):
    """Test missing notification type parameter"""
    response = client.post("/test/telegram")
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data

@pytest.mark.asyncio
async def test_telegram_service_not_configured(db):
    """Test when Telegram service is not properly configured"""
    with patch('backend.main.telegram_service') as mock_service:
        mock_service.bot = None
        mock_service.chat_id = None

        response = client.post("/test/telegram?notification_type=test")
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data

@pytest.mark.asyncio
async def test_telegram_notification_failure(mock_telegram_service, db):
    """Test handling of notification sending failure"""
    mock_telegram_service.send_test_notification = AsyncMock(return_value=False)

    response = client.post("/test/telegram?notification_type=test")
    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
