import sys
import os
import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import Base
from app.models.telegram import TelegramUser
from app.crud.crud_telegram import telegram_user

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

class TestCrudTelegram:
    @pytest.mark.asyncio
    async def test_get_by_telegram_id(self, test_db, test_user):
        """Test the get_by_telegram_id function that was causing issues."""
        # Get existing user using different approaches

        # Test 1: Using named parameter (db=test_db)
        result1 = await telegram_user.get_by_telegram_id(db=test_db, telegram_id=12345)
        assert result1 is not None
        assert result1.telegram_id == 12345
        assert result1.username == "test_user"

        # Test 2: Using positional parameter
        result2 = await telegram_user.get_by_telegram_id(test_db, telegram_id=12345)
        assert result2 is not None
        assert result2.telegram_id == 12345

        # Test 3: Test retrieving non-existent user
        non_existent = await telegram_user.get_by_telegram_id(test_db, telegram_id=99999)
        assert non_existent is None

        # Test 4: Creating and retrieving multiple users
        # Create second user
        user2 = TelegramUser(
            telegram_id=54321,
            chat_id="54321",
            username="another_user",
            is_active=True
        )
        test_db.add(user2)
        await test_db.commit()

        # Retrieve first user again
        result3 = await telegram_user.get_by_telegram_id(test_db, telegram_id=12345)
        assert result3 is not None
        assert result3.telegram_id == 12345

        # Retrieve second user
        result4 = await telegram_user.get_by_telegram_id(test_db, telegram_id=54321)
        assert result4 is not None
        assert result4.telegram_id == 54321
        assert result4.username == "another_user"

if __name__ == "__main__":
    pytest.main(["-xvs", "test_crud_telegram.py"])
