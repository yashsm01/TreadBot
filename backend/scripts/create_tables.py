import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, engine
from app.models.crypto import Cryptocurrency, CryptoPair
from app.core.logger import logger

def create_tables():
    """Create all database tables"""
    try:
        Base.metadata.drop_all(bind=engine)  # Drop existing tables
        Base.metadata.create_all(bind=engine)  # Create new tables
        logger.info("Successfully created database tables")
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")
        raise

if __name__ == "__main__":
    create_tables()
