import pytest
from sqlalchemy.orm import Session
from ..services.portfolio import PortfolioService
from ..trader.mock_exchange import MockExchange
from ..database import SessionLocal
from ..db.models import Trade, TradeStatus, TradeType, PositionType
from datetime import datetime, timedelta
from decimal import Decimal

@pytest.fixture
def db():
    """Create a test database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def portfolio_service(db):
    """Create a PortfolioService instance with mock exchange"""
    exchange = MockExchange()
    service = PortfolioService(db, exchange)
    return service

@pytest.fixture
def sample_trades(db):
    """Create sample trades for testing"""
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
            created_at=datetime.now() - timedelta(days=1),
            updated_at=datetime.now()
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
            created_at=datetime.now() - timedelta(hours=12),
            updated_at=datetime.now()
        )
    ]

    for trade in trades:
        db.add(trade)
    db.commit()

    return trades

def test_get_portfolio(portfolio_service, sample_trades, db):
    """Test getting portfolio information"""
    portfolio = portfolio_service.get_portfolio()

    assert "portfolio" in portfolio
    assert "summary" in portfolio

    # Check portfolio items
    items = portfolio["portfolio"]
    assert len(items) > 0
    for item in items:
        assert "symbol" in item
        assert "quantity" in item
        assert "avg_buy_price" in item
        assert "current_price" in item
        assert "current_value" in item
        assert "profit_loss" in item
        assert "profit_loss_pct" in item

    # Check summary
    summary = portfolio["summary"]
    assert "total_invested" in summary
    assert "total_current_value" in summary
    assert "total_profit_loss" in summary
    assert "total_profit_loss_pct" in summary

def test_get_trade_history(portfolio_service, sample_trades, db):
    """Test getting trade history"""
    history = portfolio_service.get_trade_history()

    assert len(history) > 0
    for trade in history:
        assert "coin" in trade
        assert "entry_price" in trade
        assert "exit_price" in trade
        assert "quantity" in trade
        assert "status" in trade
        assert "type" in trade
        assert "position" in trade
        assert "profit_pct" in trade
        assert "created_at" in trade
        assert "updated_at" in trade

def test_get_profit_summary(portfolio_service, sample_trades, db):
    """Test getting profit summary"""
    # Test daily summary
    daily = portfolio_service.get_profit_summary("daily")
    assert "total_trades" in daily
    assert "winning_trades" in daily
    assert "losing_trades" in daily
    assert "net_profit" in daily

    # Test weekly summary
    weekly = portfolio_service.get_profit_summary("weekly")
    assert "total_trades" in weekly
    assert "winning_trades" in weekly
    assert "losing_trades" in weekly
    assert "net_profit" in weekly

    # Test monthly summary
    monthly = portfolio_service.get_profit_summary("monthly")
    assert "total_trades" in monthly
    assert "winning_trades" in monthly
    assert "losing_trades" in monthly
    assert "net_profit" in monthly

def test_calculate_position_metrics(portfolio_service):
    """Test calculation of position metrics"""
    metrics = portfolio_service.calculate_position_metrics(
        quantity=Decimal("0.1"),
        entry_price=Decimal("50000.0"),
        current_price=Decimal("51000.0")
    )

    assert "current_value" in metrics
    assert "profit_loss" in metrics
    assert "profit_loss_pct" in metrics
    assert metrics["profit_loss"] > 0
    assert metrics["profit_loss_pct"] > 0

def test_get_open_positions(portfolio_service, sample_trades, db):
    """Test getting open positions"""
    positions = portfolio_service.get_open_positions()

    assert len(positions) > 0
    for pos in positions:
        assert pos.status == TradeStatus.OPEN
        assert pos.exit_price is None
        assert pos.profit_pct is None

def test_get_closed_positions(portfolio_service, sample_trades, db):
    """Test getting closed positions"""
    positions = portfolio_service.get_closed_positions()

    assert len(positions) > 0
    for pos in positions:
        assert pos.status == TradeStatus.CLOSED
        assert pos.exit_price is not None
        assert pos.profit_pct is not None

def test_error_handling(portfolio_service, db):
    """Test error handling"""
    # Test invalid period for profit summary
    with pytest.raises(ValueError):
        portfolio_service.get_profit_summary("invalid")

    # Test invalid position metrics calculation
    with pytest.raises(ValueError):
        portfolio_service.calculate_position_metrics(
            quantity=Decimal("-1.0"),
            entry_price=Decimal("50000.0"),
            current_price=Decimal("51000.0")
        )

def test_portfolio_updates(portfolio_service, db):
    """Test portfolio updates with new trades"""
    # Add a new trade
    new_trade = Trade(
        coin="BTC/USDT",
        entry_price=52000.0,
        exit_price=None,
        quantity=0.2,
        status=TradeStatus.OPEN,
        type=TradeType.PAPER,
        position=PositionType.LONG,
        profit_pct=None,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    db.add(new_trade)
    db.commit()

    # Check if portfolio reflects the new trade
    portfolio = portfolio_service.get_portfolio()
    btc_position = next(
        (item for item in portfolio["portfolio"] if item["symbol"] == "BTC/USDT"),
        None
    )

    assert btc_position is not None
    assert btc_position["quantity"] >= 0.2

if __name__ == "__main__":
    pytest.main(["-v", __file__])
