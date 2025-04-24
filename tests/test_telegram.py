import pytest
import os
import asyncio
from dotenv import load_dotenv
from backend.services.telegram import TelegramService
from backend.analysis.market_analyzer import MarketAnalyzer
from backend.services.portfolio import PortfolioService
from backend.trader.mock_exchange import MockExchange
from backend.database import SessionLocal
from unittest.mock import MagicMock, patch
from telegram import Update, User, Chat, Message

# Load environment variables
load_dotenv()

@pytest.fixture
async def telegram_service():
    """Create a TelegramService instance for testing"""
    # Initialize dependencies
    db = SessionLocal()
    exchange = MockExchange()
    market_analyzer = MarketAnalyzer(exchange)
    portfolio_service = PortfolioService(db, exchange)

    # Create TelegramService
    service = TelegramService(market_analyzer, portfolio_service)
    await service.initialize()

    yield service

    # Cleanup
    await service.stop()
    db.close()

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
    context = MagicMock()
    context.args = []
    return context

@pytest.mark.asyncio
async def test_initialization_without_token(telegram_service):
    """Test initialization without bot token"""
    with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': '', 'TELEGRAM_CHAT_ID': ''}):
        service = TelegramService(MagicMock(), MagicMock())
        await service.initialize()
        assert service._initialized is False

@pytest.mark.asyncio
async def test_send_message_without_initialization():
    """Test sending message without initialization"""
    service = TelegramService(MagicMock(), MagicMock())
    result = await service.send_message("Test message")
    assert result is False

@pytest.mark.asyncio
async def test_invalid_buy_command_format(telegram_service, mock_update, mock_context):
    """Test buy command with invalid format"""
    # Test with missing arguments
    mock_context.args = ["BTC/USDT"]
    await telegram_service.handle_buy(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with(
        "Invalid format. Use: /buy <symbol> <quantity> <price>\n"
        "Example: /buy BTC/USDT 0.1 50000"
    )

    # Test with invalid number format
    mock_context.args = ["BTC/USDT", "invalid", "50000"]
    await telegram_service.handle_buy(mock_update, mock_context)
    assert "Error" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_invalid_sell_command_format(telegram_service, mock_update, mock_context):
    """Test sell command with invalid format"""
    # Test with missing arguments
    mock_context.args = ["BTC/USDT"]
    await telegram_service.handle_sell(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with(
        "Invalid format. Use: /sell <symbol> <quantity> <price>\n"
        "Example: /sell BTC/USDT 0.1 51000"
    )

    # Test with invalid number format
    mock_context.args = ["BTC/USDT", "invalid", "50000"]
    await telegram_service.handle_sell(mock_update, mock_context)
    assert "Error" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_empty_portfolio(telegram_service, mock_update, mock_context):
    """Test portfolio command with empty portfolio"""
    # Mock empty portfolio response
    telegram_service.portfolio_service.get_portfolio = MagicMock(
        return_value={"portfolio": [], "summary": {}}
    )

    await telegram_service.get_portfolio(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("Your portfolio is empty.")

@pytest.mark.asyncio
async def test_invalid_profit_timeframe(telegram_service, mock_update, mock_context):
    """Test profit command with invalid timeframe"""
    mock_context.args = ["invalid_timeframe"]
    await telegram_service.get_profit(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with(
        "Invalid timeframe. Use: daily, weekly, monthly, or all"
    )

@pytest.mark.asyncio
async def test_market_analyzer_integration(telegram_service, mock_update, mock_context):
    """Test integration with MarketAnalyzer"""
    # Mock market analyzer response
    analysis_data = {
        "market_summary": {
            "last_price": 50000,
            "price_change_24h": 2.5,
            "volume_24h": 1000000
        },
        "trading_signals": {
            "trend": "bullish",
            "momentum": 1.5,
            "volume_ratio": 1.2
        },
        "volatility_metrics": {
            "volatility": 0.02,
            "price_range": 0.05
        }
    }
    telegram_service.market_analyzer.get_market_analysis = MagicMock(
        return_value=analysis_data
    )

    # Test analysis command
    mock_context.args = ["BTC/USDT", "5m"]
    await telegram_service.get_analysis(mock_update, mock_context)
    assert mock_update.message.reply_text.called
    analysis_response = mock_update.message.reply_text.call_args[0][0]
    assert "Market Analysis for BTC/USDT" in analysis_response
    assert "Price: $50,000.00" in analysis_response
    assert "Trend: BULLISH" in analysis_response

@pytest.mark.asyncio
async def test_portfolio_service_integration(telegram_service, mock_update, mock_context):
    """Test integration with PortfolioService"""
    # Mock portfolio service response
    portfolio_data = {
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
    telegram_service.portfolio_service.get_portfolio = MagicMock(
        return_value=portfolio_data
    )

    # Test portfolio command
    await telegram_service.get_portfolio(mock_update, mock_context)
    assert mock_update.message.reply_text.called
    portfolio_response = mock_update.message.reply_text.call_args[0][0]
    assert "Your Portfolio:" in portfolio_response
    assert "BTC/USDT" in portfolio_response
    assert "Total P/L: $100.00 (2.00%)" in portfolio_response

@pytest.mark.asyncio
async def test_network_error_handling(telegram_service):
    """Test handling of network errors"""
    with patch('telegram.Bot.send_message', side_effect=Exception("Network error")):
        result = await telegram_service.send_message("Test message")
        assert result is False

if __name__ == "__main__":
    pytest.main(["-v", __file__])
