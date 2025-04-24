import pytest
from fastapi.testclient import TestClient
from ..main import app
from ..database import SessionLocal, get_db
from ..db.models import Trade, Config, TradeStatus, TradeType, PositionType
from datetime import datetime
import json

# Test client setup
client = TestClient(app)

# Test database session
def override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_health_check():
    """Test the health check endpoint"""
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "exchange_type" in data
    assert "paper_trading" in data
    assert "trading_pairs" in data
    assert "default_pair" in data

def test_get_trades(db):
    """Test getting trades with different filters"""
    # Add some test trades
    trades = [
        Trade(
            coin="BTC/USDT",
            entry_price=50000.0,
            exit_price=51000.0,
            quantity=0.1,
            status=TradeStatus.CLOSED,
            type=TradeType.PAPER,
            position=PositionType.LONG,
            profit_pct=2.0,
            created_at=datetime.now()
        ),
        Trade(
            coin="ETH/USDT",
            entry_price=3000.0,
            exit_price=None,
            quantity=1.0,
            status=TradeStatus.OPEN,
            type=TradeType.PAPER,
            position=PositionType.LONG,
            profit_pct=None,
            created_at=datetime.now()
        )
    ]
    for trade in trades:
        db.add(trade)
    db.commit()

    # Test without filters
    response = client.get("/trades")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

    # Test with status filter
    response = client.get("/trades?status=OPEN")
    assert response.status_code == 200

    # Test with coin filter
    response = client.get("/trades?coin=BTC/USDT")
    assert response.status_code == 200

    # Test with limit
    response = client.get("/trades?limit=10")
    assert response.status_code == 200
    assert len(response.json()) <= 10

def test_get_profit_summary(db):
    """Test getting profit summary for different periods"""
    periods = ["daily", "weekly", "monthly"]
    for period in periods:
        response = client.get(f"/trades/profit-summary?period={period}")
        assert response.status_code == 200
        data = response.json()
        assert "total_trades" in data
        assert "winning_trades" in data
        assert "losing_trades" in data
        assert "net_profit" in data

def test_get_config(db):
    """Test getting trading configuration"""
    # Add test config
    config = Config(
        coin="BTC/USDT",
        interval="5m",
        breakout_pct=1.0,
        tp_pct=2.0,
        sl_pct=1.0,
        quantity=0.1
    )
    db.add(config)
    db.commit()

    # Test without filter
    response = client.get("/config")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

    # Test with coin filter
    response = client.get("/config?coin=BTC/USDT")
    assert response.status_code == 200

def test_update_config(db):
    """Test updating trading configuration"""
    config_data = {
        "interval": "5m",
        "breakout_pct": 1.0,
        "tp_pct": 2.0,
        "sl_pct": 1.0,
        "quantity": 0.1
    }
    response = client.post(
        "/config/update?coin=BTC/USDT",
        json=config_data
    )
    assert response.status_code == 200
    data = response.json()
    assert data["coin"] == "BTC/USDT"
    assert data["interval"] == config_data["interval"]
    assert data["breakout_pct"] == config_data["breakout_pct"]

def test_manual_trade(db):
    """Test manual trade execution"""
    trade_data = {
        "symbol": "BTC/USDT",
        "quantity": 0.1,
        "breakout_pct": 1.0,
        "tp_pct": 2.0,
        "sl_pct": 1.0,
        "position": "LONG"
    }
    response = client.post("/trade/manual", json=trade_data)
    assert response.status_code == 200
    data = response.json()
    assert "trade_id" in data
    assert data["status"] == "success"

def test_market_analysis(db):
    """Test market analysis endpoints"""
    # Test single pair analysis
    response = client.get("/analysis/market?symbol=BTC/USDT&timeframe=5m")
    assert response.status_code == 200
    data = response.json()
    assert "market_summary" in data
    assert "trading_signals" in data
    assert "volatility_metrics" in data

    # Test all pairs analysis
    response = client.get("/analysis/market/all?timeframe=5m")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert len(data) > 0

def test_telegram_notifications(db):
    """Test Telegram notification endpoints"""
    notification_types = ["trade", "error", "summary", "test"]
    for n_type in notification_types:
        response = client.post(f"/test/telegram?notification_type={n_type}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

def test_error_handling():
    """Test error handling for invalid requests"""
    # Test invalid trade status
    response = client.get("/trades?status=INVALID")
    assert response.status_code == 422

    # Test invalid period
    response = client.get("/trades/profit-summary?period=invalid")
    assert response.status_code == 422

    # Test invalid timeframe
    response = client.get("/analysis/market?symbol=BTC/USDT&timeframe=invalid")
    assert response.status_code == 422

    # Test missing required parameters
    response = client.get("/analysis/market")
    assert response.status_code == 422

if __name__ == "__main__":
    pytest.main(["-v", __file__])
