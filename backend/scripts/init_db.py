import os
import sys
import logging

# Add the parent directory to sys.path
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from database import Base, engine
from models.portfolio import Portfolio, Transaction, StraddleInterval

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    """Initialize the database by creating all tables"""
    try:
        logger.info("Creating database tables...")

        # Create tables
        Base.metadata.create_all(bind=engine)

        logger.info("Created table: portfolios")
        logger.info("Created table: transactions")
        logger.info("Created table: straddle_intervals")

        logger.info("Database initialization completed successfully!")
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")
        raise

if __name__ == "__main__":
    init_db()
