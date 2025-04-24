import pytest
import asyncio
from unittest.mock import MagicMock, patch
from backend.services.telegram import TelegramService
from backend.analysis.market_analyzer import MarketAnalyzer
from backend.services.portfolio import PortfolioService
from telegram import Update, User, Chat, Message
from telegram.ext import ContextTypes

@pytest.fixture
def mock_update():
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    chat = MagicMock(spec=Chat)
    message = MagicMock(spec=Message)

    user.id = 505504650
    chat.id = 505504650
    message.chat = chat
    message.from_user = user
    update.message = message
    update.effective_user = user

    return update

@pytest.fixture
def mock_context():
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []
    return context

@pytest.fixture
async def telegram_service():
    market_analyzer = MagicMock(spec=MarketAnalyzer)
    portfolio_service = MagicMock(spec=PortfolioService)

    # Mock market analyzer methods
    market_analyzer.get_supported_pairs.return_value = ["BTC/USDT", "ETH/USDT"]
    market_analyzer.get_trading_signals.return_value = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "current_price": 50000,
        "sma20": 49800,
        "sma50": 49500,
        "momentum": 1.5,
        "volume_ratio": 1.2,
        "trend": "bullish",
        "timestamp": "2025-04-24T10:00:00"
    }
    market_analyzer.get_market_analysis.return_value = {
        "symbol": "BTC/USDT",
        "timeframe": "5m",
        "volatility_metrics": {
            "volatility": 0.02,
            "avg_price": 50000,
            "price_range": 0.05
        },
        "market_summary": {
            "last_price": 50000,
            "bid": 49990,
            "ask": 50010,
            "volume_24h": 1000,
            "price_change_24h": 2.5,
            "high_24h": 51000,
            "low_24h": 49000
        },
        "trading_signals": {
            "current_price": 50000,
            "sma20": 49800,
            "sma50": 49500,
            "momentum": 1.5,
            "volume_ratio": 1.2,
            "trend": "bullish",
            "timestamp": "2025-04-24T10:00:00"
        },
        "timestamp": "2025-04-24T10:00:00"
    }

    # Mock portfolio service methods
    portfolio_service.add_transaction.return_value = {
        "symbol": "BTC/USDT",
        "quantity": 0.1,
        "price": 50000,
        "total": 5000
    }

    portfolio_service.get_portfolio.return_value = {
        "portfolio": [{
            "symbol": "BTC/USDT",
            "quantity": 0.1,
            "avg_buy_price": 50000,
            "current_price": 51000,
            "current_value": 5100,
            "profit_loss": 100,
            "profit_loss_pct": 2.0
        }],
        "summary": {
            "total_invested": 5000,
            "total_current_value": 5100,
            "total_profit_loss": 100,
            "total_profit_loss_pct": 2.0
        }
    }

    service = TelegramService(market_analyzer, portfolio_service)
    service._initialized = True  # Skip actual Telegram initialization
    return service

@pytest.mark.asyncio
async def test_start_command(telegram_service, mock_update, mock_context):
    await telegram_service._handle_start(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    assert "Welcome" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_help_command(telegram_service, mock_update, mock_context):
    await telegram_service.help(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    assert "Available commands" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_pairs_command(telegram_service, mock_update, mock_context):
    await telegram_service.get_pairs(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    text = mock_update.message.reply_text.call_args[0][0]
    assert "BTC/USDT" in text
    assert "ETH/USDT" in text

@pytest.mark.asyncio
async def test_analysis_command(telegram_service, mock_update, mock_context):
    mock_context.args = ["BTC/USDT"]
    await telegram_service.get_analysis(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    text = mock_update.message.reply_text.call_args[0][0]
    assert "Market Analysis for BTC/USDT" in text

@pytest.mark.asyncio
async def test_buy_command(telegram_service, mock_update, mock_context):
    mock_context.args = ["BTC/USDT", "0.1", "50000"]
    await telegram_service.handle_buy(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    text = mock_update.message.reply_text.call_args[0][0]
    assert "Buy order recorded" in text

@pytest.mark.asyncio
async def test_sell_command(telegram_service, mock_update, mock_context):
    mock_context.args = ["BTC/USDT", "0.1", "51000"]
    await telegram_service.handle_sell(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    text = mock_update.message.reply_text.call_args[0][0]
    assert "Sell order recorded" in text

@pytest.mark.asyncio
async def test_portfolio_command(telegram_service, mock_update, mock_context):
    await telegram_service.get_portfolio(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    text = mock_update.message.reply_text.call_args[0][0]
    assert "Your Portfolio" in text
    assert "BTC/USDT" in text

@pytest.mark.asyncio
async def test_invalid_buy_command(telegram_service, mock_update, mock_context):
    mock_context.args = ["BTC/USDT"]  # Missing quantity and price
    await telegram_service.handle_buy(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    text = mock_update.message.reply_text.call_args[0][0]
    assert "Invalid format" in text

@pytest.mark.asyncio
async def test_invalid_analysis_command(telegram_service, mock_update, mock_context):
    mock_context.args = []  # Missing symbol
    await telegram_service.get_analysis(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    text = mock_update.message.reply_text.call_args[0][0]
    assert "Usage" in text

@pytest.mark.asyncio
async def test_signals_command(telegram_service, mock_update, mock_context):
    mock_context.args = ["BTC/USDT"]
    await telegram_service.get_signals(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    text = mock_update.message.reply_text.call_args[0][0]
    assert "Trading Signals for BTC/USDT" in text
    assert "Trend: BULLISH" in text

@pytest.mark.asyncio
async def test_history_command(telegram_service, mock_update, mock_context):
    # Mock get_transaction_history
    telegram_service.portfolio_service.get_transaction_history.return_value = [
        {
            "type": "BUY",
            "symbol": "BTC/USDT",
            "quantity": 0.1,
            "price": 50000,
            "total": 5000,
            "timestamp": "2025-04-24T10:00:00"
        }
    ]

    mock_context.args = ["BTC/USDT"]
    await telegram_service.get_history(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    text = mock_update.message.reply_text.call_args[0][0]
    assert "Transaction History" in text
    assert "BTC/USDT" in text

@pytest.mark.asyncio
async def test_profit_command(telegram_service, mock_update, mock_context):
    # Mock get_profit_summary
    telegram_service.portfolio_service.get_profit_summary.return_value = {
        "total_invested": 5000,
        "total_current_value": 5100,
        "total_profit_loss": 100,
        "total_profit_loss_pct": 2.0,
        "total_trades": 2,
        "timestamp": "2025-04-24T10:00:00"
    }

    mock_context.args = ["daily"]
    await telegram_service.get_profit(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    text = mock_update.message.reply_text.call_args[0][0]
    assert "Profit Summary" in text
    assert "Total P/L: $100" in text

@pytest.mark.asyncio
async def test_invalid_sell_command(telegram_service, mock_update, mock_context):
    mock_context.args = ["BTC/USDT"]  # Missing quantity and price
    await telegram_service.handle_sell(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    text = mock_update.message.reply_text.call_args[0][0]
    assert "Invalid format" in text

@pytest.mark.asyncio
async def test_invalid_signals_command(telegram_service, mock_update, mock_context):
    mock_context.args = []  # Missing symbol
    await telegram_service.get_signals(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    text = mock_update.message.reply_text.call_args[0][0]
    assert "Usage" in text

@pytest.mark.asyncio
async def test_empty_portfolio(telegram_service, mock_update, mock_context):
    # Mock empty portfolio
    telegram_service.portfolio_service.get_portfolio.return_value = {
        "portfolio": [],
        "summary": {
            "total_invested": 0,
            "total_current_value": 0,
            "total_profit_loss": 0,
            "total_profit_loss_pct": 0
        }
    }

    await telegram_service.get_portfolio(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    text = mock_update.message.reply_text.call_args[0][0]
    assert "Your portfolio is empty" in text

@pytest.mark.asyncio
async def test_empty_history(telegram_service, mock_update, mock_context):
    # Mock empty history
    telegram_service.portfolio_service.get_transaction_history.return_value = []

    mock_context.args = ["BTC/USDT"]
    await telegram_service.get_history(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    text = mock_update.message.reply_text.call_args[0][0]
    assert "No transactions found" in text

if __name__ == "__main__":
    pytest.main(["-v", "test_telegram_bot.py"])
