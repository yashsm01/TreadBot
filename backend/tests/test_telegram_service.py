import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import event, select

from app.core.database import Base
from app.models.telegram import TelegramUser, TelegramNotification
from app.crud.crud_telegram import telegram_user, telegram_notification
from app.services.telegram_service import TelegramService
from app.services.market_analyzer import MarketAnalyzer
from app.services.portfolio_service import PortfolioService
from app.services.straddle_service import StraddleService
from app.services.helper.binance_helper import BinanceHelper

# Test database URL - use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def test_db():
    """Create a test database and yield a session."""
    engine = create_async_engine(TEST_DATABASE_URL)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create async session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

@pytest.fixture
async def test_telegram_service(test_db):
    """Create a test telegram service instance with mocked dependencies."""
    # Create mocks for dependencies
    market_analyzer_mock = AsyncMock(spec=MarketAnalyzer)
    portfolio_service_mock = AsyncMock(spec=PortfolioService)
    straddle_service_mock = AsyncMock(spec=StraddleService)
    binance_helper_mock = AsyncMock(spec=BinanceHelper)

    # Create service with mocked dependencies
    service = TelegramService(
        db=test_db,
        market_analyzer=market_analyzer_mock,
        portfolio_service=portfolio_service_mock,
        straddle_service=straddle_service_mock,
        binance_helper=binance_helper_mock
    )

    # Mock the telegram bot
    service.application = AsyncMock()
    service._initialized = True

    return service

@pytest.fixture
async def test_user(test_db):
    """Create a test telegram user in the database."""
    user = TelegramUser(
        telegram_id=12345,
        chat_id="12345",
        username="test_user",
        is_active=True,
        created_at=datetime.utcnow(),
        last_interaction=datetime.utcnow()
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user

class TestTelegramService:
    @pytest.mark.asyncio
    async def test_user_crud_operations(self, test_db, test_telegram_service):
        """Test basic CRUD operations on TelegramUser."""
        # Create a test user
        new_user = TelegramUser(
            telegram_id=54321,
            chat_id="54321",
            username="new_test_user",
            is_active=True
        )
        test_db.add(new_user)
        await test_db.commit()

        # Test get_by_telegram_id
        result = await telegram_user.get_by_telegram_id(test_db, telegram_id=54321)
        assert result is not None
        assert result.telegram_id == 54321
        assert result.username == "new_test_user"

        # Test updating a user
        result.is_active = False
        test_db.add(result)
        await test_db.commit()
        await test_db.refresh(result)

        # Get the user again to verify update
        updated_result = await telegram_user.get_by_telegram_id(test_db, telegram_id=54321)
        assert updated_result is not None
        assert updated_result.is_active == False

        # Test get_active_users
        active_users = await telegram_user.get_active_users(test_db)
        # Should be empty since we set the only user to inactive
        assert len(active_users) == 0

        # Set user to active
        updated_result.is_active = True
        test_db.add(updated_result)
        await test_db.commit()

        # Test get_active_users again
        active_users = await telegram_user.get_active_users(test_db)
        assert len(active_users) == 1

    @pytest.mark.asyncio
    async def test_notification_crud_operations(self, test_db, test_user):
        """Test CRUD operations on TelegramNotification."""
        # Create a test notification
        notification = TelegramNotification(
            user_id=test_user.id,
            message_type="TEST",
            content="Test notification",
            symbol="BTC/USDT",
            is_sent=False
        )
        test_db.add(notification)
        await test_db.commit()
        await test_db.refresh(notification)

        # Test get_pending_notifications
        pending = await telegram_notification.get_pending_notifications(test_db)
        assert len(pending) == 1
        assert pending[0].content == "Test notification"

        # Test mark_as_sent
        updated = await telegram_notification.mark_as_sent(test_db, notification_id=notification.id)
        assert updated is not None
        assert updated.is_sent == True

        # Test get_pending_notifications again
        pending = await telegram_notification.get_pending_notifications(test_db)
        assert len(pending) == 0

        # Test get_user_notifications
        user_notifications = await telegram_notification.get_user_notifications(test_db, user_id=test_user.id)
        assert len(user_notifications) == 1
        assert user_notifications[0].content == "Test notification"

    @pytest.mark.asyncio
    async def test_handle_start_command(self, test_db, test_telegram_service):
        """Test the _handle_start command with an existing user."""
        # Create a mock update
        update = AsyncMock()
        update.effective_user.id = 12345
        update.effective_chat.id = 12345
        update.effective_user.username = "test_user"

        # Create a test user
        user = TelegramUser(
            telegram_id=12345,
            chat_id="12345",
            username="test_user",
            is_active=False
        )
        test_db.add(user)
        await test_db.commit()

        # Call the handler
        context = MagicMock()
        await test_telegram_service._handle_start(update, context)

        # Verify the user was updated
        updated_user = await telegram_user.get_by_telegram_id(test_db, telegram_id=12345)
        assert updated_user is not None
        assert updated_user.is_active == True

        # Verify reply_text was called
        update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_stop_command(self, test_db, test_telegram_service, test_user):
        """Test the _handle_stop command."""
        # Create a mock update
        update = AsyncMock()
        update.effective_user.id = test_user.telegram_id

        # Call the handler
        context = MagicMock()
        await test_telegram_service._handle_stop(update, context)

        # Verify the user was updated
        updated_user = await telegram_user.get_by_telegram_id(test_db, telegram_id=test_user.telegram_id)
        assert updated_user is not None
        assert updated_user.is_active == False

        # Verify reply_text was called
        update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_update_command(self, test_db, test_telegram_service, test_user):
        """Test the _handle_update_command."""
        # Create a mock update
        update = AsyncMock()
        update.effective_user.id = test_user.telegram_id

        # Call the handler
        context = MagicMock()
        await test_telegram_service._handle_update_command(update, context)

        # Verify the user was updated
        updated_user = await telegram_user.get_by_telegram_id(test_db, telegram_id=test_user.telegram_id)
        assert updated_user is not None
        assert updated_user.last_interaction is not None

        # Verify reply_text was called
        update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_status_command(self, test_db, test_telegram_service, test_user):
        """Test the _handle_status command."""
        # Create a mock update
        update = AsyncMock()
        update.effective_user.id = test_user.telegram_id

        # Call the handler
        context = MagicMock()
        await test_telegram_service._handle_status(update, context)

        # Verify reply_text was called
        update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_notification(self, test_db, test_telegram_service, test_user):
        """Test the send_notification method."""
        # Set up the bot mock
        test_telegram_service.application.bot = AsyncMock()

        # Call the method
        result = await test_telegram_service.send_notification(
            user_id=test_user.telegram_id,
            message_type="TEST",
            content="Test notification content",
            symbol="BTC/USDT"
        )

        # Verify the result
        assert result == True

        # Verify a notification was created in the database
        notifications = await telegram_notification.get_user_notifications(test_db, user_id=test_user.id)
        assert len(notifications) == 1
        assert notifications[0].content == "Test notification content"
        assert notifications[0].is_sent == True

        # Verify the bot send_message was called
        test_telegram_service.application.bot.send_message.assert_called_once()

if __name__ == "__main__":
    pytest.main(["-xvs", "test_telegram_service.py"])
