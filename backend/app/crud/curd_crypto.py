from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text
from sqlalchemy.exc import SQLAlchemyError
from app.services.helper.binance_helper import BinanceHelper
from app.core.exchange.exchange_manager import exchange_manager
from datetime import datetime
import re
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

async def table_exists(db: AsyncSession, table_name: str) -> bool:
    """Check if a table exists in the database

    Args:
        db: The database session
        table_name: The name of the table to check

    Returns:
        True if the table exists, False otherwise
    """
    try:
        # This query works for PostgreSQL
        query = text(f"""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = '{table_name}'
        );
        """)
        # Execute with proper async pattern
        result = await db.execute(query)
        # Use scalar() instead of scalar_one() to handle case when no row exists
        exists = result.scalar()
        return bool(exists) if exists is not None else False
    except Exception as e:
        logger.error(f"Error checking if table exists: {str(e)}")
        return False

def sanitize_table_name(name: str, month: int = None, year: int = None) -> str:
    """Sanitize table name for SQL safety and append month/year if provided

    Args:
        name: The raw table name, potentially with invalid characters
        month: Optional month to append (1-12)
        year: Optional year to append

    Returns:
        A sanitized table name safe for SQL with optional MM_YYYY suffix
    """
    # Replace / with _ and other special characters
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)

    # Append month and year if provided
    if month is not None and year is not None:
        # Format as MM_YYYY
        sanitized = f"{sanitized}_{month:02d}_{year}"

    return sanitized

def validate_inputs(symbol: str, month: int = None, year: int = None) -> Tuple[str, bool]:
    """Validate and sanitize input symbol and optional month/year

    Args:
        symbol: The cryptocurrency symbol
        month: Optional month (1-12)
        year: Optional year

    Returns:
        Tuple of (sanitized_symbol, is_valid)
    """
    # Validate symbol
    if not symbol or not isinstance(symbol, str):
        logger.error(f"Invalid symbol: {symbol}")
        return symbol, False

    # Validate month and year if provided
    if month is not None:
        if not isinstance(month, int) or month < 1 or month > 12:
            logger.error(f"Invalid month: {month}")
            return symbol, False

    if year is not None:
        if not isinstance(year, int) or year < 2000 or year > 2100:
            logger.error(f"Invalid year: {year}")
            return symbol, False

    # Sanitize symbol to ensure it's SQL safe
    sanitized_symbol = sanitize_table_name(symbol, month, year)
    return sanitized_symbol, True

async def create_crypto_table(db: AsyncSession, symbol: str, month: int = None, year: int = None) -> bool:
    """Create a cryptocurrency table with the symbol name and optional month/year

    Args:
        db: The database session
        symbol: The cryptocurrency symbol (e.g., 'BTC/USDT')
        month: Optional month (1-12)
        year: Optional year

    Returns:
        True if table was created successfully, False otherwise
    """
    try:
        # Get current month/year if not provided
        if month is None or year is None:
            from datetime import datetime
            now = datetime.now()
            month = month or now.month
            year = year or now.year

        # Validate input
        sanitized_symbol, is_valid = validate_inputs(symbol, month, year)
        if not is_valid:
            logger.error(f"Invalid input: symbol={symbol}, month={month}, year={year}")
            return False

        # Create table name
        table_name = sanitized_symbol

        # Check if table already exists
        exists = await table_exists(db, table_name)
        if exists:
            logger.info(f"Table {table_name} already exists, skipping creation")
            return True

        try:
            # Create table
            await db.execute(text(f'''
            CREATE TABLE IF NOT EXISTS "{table_name}" (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(50) NOT NULL,
                    name VARCHAR(100),
                    current_price NUMERIC(18, 8),  -- better precision than FLOAT
                    swap_transactions_id VARCHAR(255),  -- add REFERENCES if foreign key
                    timestamp TIMESTAMP,      -- renamed to avoid confusion
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            '''))

            # Create index on symbol
            await db.execute(text(f'''
                CREATE INDEX IF NOT EXISTS "idx_{table_name}_symbol"
                ON "{table_name}" (symbol);
            '''))

            # Create index on timestamp
            await db.execute(text(f'''
                CREATE INDEX IF NOT EXISTS "idx_{table_name}_timestamp"
                ON "{table_name}" (timestamp);
            '''))

            # Finally commit
            await db.commit()

            logger.info(f"Created table and indexes for: {table_name}")

            return True

        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"SQLAlchemy error creating table {table_name}: {str(e)}")
            return False
        except Exception as e:
            await db.rollback()
            logger.error(f"Unexpected error creating table {table_name}: {str(e)}")
            return False

    except Exception as e:
        # Catch-all for any unhandled exceptions
        logger.error(f"Critical error in create_crypto_table: {str(e)}")
        return False

async def insert_crypto_data(db: AsyncSession, symbol: str, data: dict, month: int = None, year: int = None, swap_transaction_id: str = None) -> bool:
    """Insert data into a cryptocurrency table

    Args:
        db: The database session
        symbol: The cryptocurrency symbol (e.g., 'BTC/USDT')
        data: Dictionary containing data to insert (must have current_price, timestamp fields)
        month: Optional month (1-12)
        year: Optional year
        swap_transaction_id: Optional swap transaction id
    Returns:
        True if data was inserted successfully, False otherwise
    """
    try:
        # Get current month/year if not provided
        if month is None or year is None:
            from datetime import datetime
            now = datetime.now()
            month = month or now.month
            year = year or now.year

        # Validate input
        sanitized_symbol, is_valid = validate_inputs(symbol, month, year)
        if not is_valid:
            logger.error(f"Invalid input: symbol={symbol}, month={month}, year={year}")
            return False

        # Create table name
        table_name = sanitized_symbol

        # Check if table exists
        exists = await table_exists(db, table_name)
        if not exists:
            logger.error(f"Table {table_name} does not exist, cannot insert data")
            success = await create_crypto_table(db, symbol, month, year)
            logger.info(f"Created table and indexes for: {table_name}")
            return False

        # Validate required data fields
        required_fields = ['current_price', 'timestamp']
        for field in required_fields:
            if field not in data:
                logger.error(f"Missing required field: {field}")
                return False

        try:
            # Set timestamp if not provided, ensure it's timezone-naive
            from datetime import datetime
            if 'created_at' not in data:
                data['created_at'] = datetime.now()

            # Ensure timestamp is timezone-naive for consistency
            if hasattr(data['timestamp'], 'tzinfo') and data['timestamp'].tzinfo is not None:
                # Convert to naive datetime by replacing with the same values but no timezone
                timestamp = data['timestamp'].replace(tzinfo=None)
            else:
                timestamp = data['timestamp']

            # Similarly ensure created_at is timezone-naive
            if hasattr(data['created_at'], 'tzinfo') and data['created_at'].tzinfo is not None:
                created_at = data['created_at'].replace(tzinfo=None)
            else:
                created_at = data['created_at']

            # Insert data
            insert_query = text(f"""
            INSERT INTO "{table_name}" (symbol, name, current_price, swap_transactions_id, timestamp, created_at)
            VALUES (:symbol, :name, :current_price, :swap_transactions_id, :timestamp, :created_at)
            RETURNING id
            """)

            # Execute insert
            result = await db.execute(
                insert_query,
                {
                    'symbol': symbol,
                    'name': data.get('name', symbol),
                    'current_price': data['current_price'],
                    'swap_transactions_id': data.get('swap_transactions_id', swap_transaction_id),
                    'timestamp': timestamp,
                    'created_at': created_at
                }
            )

            # Get inserted ID
            inserted_id = result.scalar_one()

            # Commit the transaction
            await db.commit()

            logger.info(f"Inserted data into {table_name} with ID {inserted_id}")
            return True

        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"SQLAlchemy error inserting data into {table_name}: {str(e)}")
            return False
        except Exception as e:
            await db.rollback()
            logger.error(f"Unexpected error inserting data into {table_name}: {str(e)}")
            return False

    except Exception as e:
        # Catch-all for any unhandled exceptions
        logger.error(f"Critical error in insert_crypto_data: {str(e)}")
        return False

async def insert_crypto_data_live(db: AsyncSession, symbol: str, swap_transaction_id: str = None) -> bool:
    """Insert live cryptocurrency data into a table

    Args:
        db: The database session
        symbol: The cryptocurrency symbol (e.g., 'BTC/USDT')

    Returns:
        True if data was inserted successfully, False otherwise
    """
    try:
        # Get ticker data from exchange
        ticker = await exchange_manager.get_ticker(symbol.replace("/", ""))
        if not ticker:
            raise Exception(f"Could not get ticker data for {symbol}")

        get_price = ticker
        get_price['symbol'] = symbol
        get_price['name'] = symbol.replace("/", "")
        get_price['current_price'] = float(ticker['last'])

        # Use timestamp from ticker if available, otherwise use current time
        if 'timestamp' in ticker and ticker['timestamp']:
            # Convert Unix timestamp in milliseconds to datetime object
            get_price['timestamp'] = datetime.fromtimestamp(ticker['timestamp'] / 1000)
        else:
            # Fallback to current time if ticker doesn't provide timestamp
            get_price['timestamp'] = datetime.now()

        print(get_price)
        await insert_crypto_data(db, symbol, get_price, swap_transaction_id=swap_transaction_id)
        return get_price
    except Exception as e:
        logger.error(f"Critical error in insert_crypto_data_live: {str(e)}")
        return False
