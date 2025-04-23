import os
import sys
import logging
from dotenv import load_dotenv
import uvicorn
from pathlib import Path

# Add the project root directory to Python path
project_root = str(Path(__file__).parent)
sys.path.append(project_root)

# Load environment variables
load_dotenv()

# Verify required environment variables
required_vars = [
    "DATABASE_URL",
    "HOST",
    "PORT",
    "LOG_LEVEL",
    "LOG_FORMAT",
    "DEFAULT_INTERVAL",
    "DEFAULT_BREAKOUT_PCT",
    "DEFAULT_TP_PCT",
    "DEFAULT_SL_PCT",
    "DEFAULT_QUANTITY",
    "PAPER_TRADING",
    "TRADING_PAIRS",
    "DEFAULT_TRADING_PAIR",
    "ALLOWED_ORIGINS"
]

missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

from backend.db.models import Base, get_db_engine
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format=os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
logger = logging.getLogger(__name__)

def setup_database():
    """Initialize database and create tables"""
    try:
        # Get database URL
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL not found in environment variables")

        # Create database engine
        engine = get_db_engine()

        # Create tables
        Base.metadata.create_all(engine)

        # Create session factory
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        logger.info("Database setup completed successfully")
        return SessionLocal
    except Exception as e:
        logger.error(f"Error setting up database: {str(e)}")
        sys.exit(1)

def main():
    """Main function to run the application"""
    try:
        # Setup database
        SessionLocal = setup_database()

        # Start the application
        uvicorn.run(
            "backend.main:app",
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", 8000)),
            reload=True,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Error running application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
