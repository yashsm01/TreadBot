import sys
import os
import asyncio
import pytest
from datetime import datetime

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import SessionLocal
from app.models.telegram import TelegramUser
from app.crud.crud_telegram import telegram_user

# Test user data
TEST_TELEGRAM_ID = 999999  # Use a unique ID for testing

async def test_postgres_connection():
    """Test async PostgreSQL connection and CRUD operations."""
    print("Testing PostgreSQL connection...")

    # Use the actual database connection from settings
    async with SessionLocal() as db:
        try:
            # 1. Check if test user exists and delete it if it does
            print("Checking if test user exists...")
            existing_user = await telegram_user.get_by_telegram_id(db, telegram_id=TEST_TELEGRAM_ID)
            if existing_user:
                print(f"Deleting existing test user with ID {TEST_TELEGRAM_ID}...")
                await db.delete(existing_user)
                await db.commit()

            # 2. Create a new test user
            print("Creating new test user...")
            new_user = TelegramUser(
                telegram_id=TEST_TELEGRAM_ID,
                chat_id=str(TEST_TELEGRAM_ID),
                username="test_postgres_user",
                is_active=True,
                created_at=datetime.utcnow(),
                last_interaction=datetime.utcnow()
            )
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            print(f"Created user: {new_user.telegram_id} - {new_user.username}")

            # 3. Fetch the user
            print("Fetching user by telegram_id...")
            fetched_user = await telegram_user.get_by_telegram_id(db, telegram_id=TEST_TELEGRAM_ID)
            print(f"Fetched user: {fetched_user.telegram_id} - {fetched_user.username}")
            assert fetched_user is not None
            assert fetched_user.telegram_id == TEST_TELEGRAM_ID
            assert fetched_user.username == "test_postgres_user"

            # 4. Update the user
            print("Updating user...")
            fetched_user.is_active = False
            db.add(fetched_user)
            await db.commit()
            await db.refresh(fetched_user)

            # 5. Verify update
            print("Verifying update...")
            updated_user = await telegram_user.get_by_telegram_id(db, telegram_id=TEST_TELEGRAM_ID)
            assert updated_user is not None
            assert updated_user.is_active == False
            print(f"Updated user active status: {updated_user.is_active}")

            # 6. Delete the test user
            print("Cleaning up - deleting test user...")
            await db.delete(updated_user)
            await db.commit()

            # 7. Verify deletion
            final_check = await telegram_user.get_by_telegram_id(db, telegram_id=TEST_TELEGRAM_ID)
            assert final_check is None
            print("User successfully deleted")

            print("All PostgreSQL async operations completed successfully!")
            return True

        except Exception as e:
            print(f"Error during PostgreSQL testing: {str(e)}")
            await db.rollback()
            raise
        finally:
            await db.close()

if __name__ == "__main__":
    asyncio.run(test_postgres_connection())
