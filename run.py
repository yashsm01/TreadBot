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

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format=os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
logger = logging.getLogger(__name__)

# Required environment variables
required_vars = [
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
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
    "ALLOWED_ORIGINS",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID"
]

def check_environment():
    """Check if all required environment variables are set"""
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)

def main():
    """Main function to run the application"""
    try:
        # Check environment variables
        check_environment()

        # Start the application
        uvicorn.run(
            "backend.main:app",
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", 8000)),
            reload=True,
            log_level=os.getenv("LOG_LEVEL", "info").lower()
        )
    except Exception as e:
        logger.error(f"Error running application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
