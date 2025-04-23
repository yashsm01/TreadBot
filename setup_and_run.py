import os
import sys
import subprocess
import logging
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_environment():
    """Set up the Python environment"""
    try:
        # Create virtual environment if it doesn't exist
        if not os.path.exists("venv"):
            logger.info("Creating virtual environment...")
            subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)

        # Determine the pip path based on OS
        if os.name == "nt":  # Windows
            pip_path = os.path.join("venv", "Scripts", "pip")
        else:  # Unix/MacOS
            pip_path = os.path.join("venv", "bin", "pip")

        # Install requirements
        logger.info("Installing requirements...")
        subprocess.run([pip_path, "install", "-r", "requirements.txt"], check=True)
        subprocess.run([pip_path, "install", "-r", "requirements-test.txt"], check=True)

        logger.info("Environment setup completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error setting up environment: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)

def create_env_file():
    """Create .env file if it doesn't exist"""
    env_content = """# Database Configuration
DATABASE_URL=postgresql://postgres:1234@localhost:5432/crypto_trading

# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=true

# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s

# Trading Configuration
DEFAULT_INTERVAL=5m
DEFAULT_BREAKOUT_PCT=0.5
DEFAULT_TP_PCT=1.0
DEFAULT_SL_PCT=0.5
DEFAULT_QUANTITY=0.001

# Paper Trading Mode (true/false)
PAPER_TRADING=true

# Trading Pairs Configuration
TRADING_PAIRS=BTC/USDT,ETH/USDT,BNB/USDT,GUN/USDT
DEFAULT_TRADING_PAIR=BTC/USDT

# CORS Configuration
ALLOWED_ORIGINS=http://localhost:4200,http://localhost:3000

# Telegram Bot Configuration (Optional for testing)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here

# Binance API Configuration (Optional for testing)
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_API_SECRET=your_binance_api_secret_here
"""

    try:
        if not os.path.exists(".env"):
            logger.info("Creating .env file...")
            with open(".env", "w") as f:
                f.write(env_content)
            logger.info(".env file created successfully")

        # Verify .env file exists and can be loaded
        load_dotenv()
        if not os.getenv("DATABASE_URL"):
            raise ValueError("DATABASE_URL not found in .env file")

        logger.info("Environment variables loaded successfully")
    except Exception as e:
        logger.error(f"Error with .env file: {str(e)}")
        sys.exit(1)

def setup_database():
    """Set up the PostgreSQL database"""
    try:
        # Check if psql is available
        try:
            if os.name == "nt":  # Windows
                subprocess.run(["where", "psql"], check=True, capture_output=True)
            else:  # Unix/MacOS
                subprocess.run(["which", "psql"], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            logger.error("psql command not found. Please make sure PostgreSQL is installed and added to your system PATH.")
            logger.info("You can manually create the database using pgAdmin or psql with these credentials:")
            logger.info("Username: postgres")
            logger.info("Password: 1234")
            logger.info("Database: crypto_trading")
            return

        # Create database using psql
        if os.name == "nt":  # Windows
            try:
                subprocess.run([
                    "psql",
                    "-U", "postgres",
                    "-c", "CREATE DATABASE crypto_trading;"
                ], check=True, env=dict(os.environ, PGPASSWORD="1234"))
            except subprocess.CalledProcessError as e:
                if "already exists" in str(e):
                    logger.info("Database already exists, continuing...")
                else:
                    raise
        else:  # Unix/MacOS
            try:
                subprocess.run([
                    "sudo", "-u", "postgres",
                    "psql",
                    "-c", "CREATE DATABASE crypto_trading;"
                ], check=True)
            except subprocess.CalledProcessError as e:
                if "already exists" in str(e):
                    logger.info("Database already exists, continuing...")
                else:
                    raise

        logger.info("Database setup completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error creating database: {str(e)}")
        logger.info("Please make sure PostgreSQL is running and accessible with the provided credentials.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)

def main():
    """Main function to set up and run the application"""
    try:
        # Set up environment
        setup_environment()

        # Create and verify .env file
        create_env_file()

        # Set up database
        setup_database()

        # Run the application
        logger.info("Starting the application...")
        if os.name == "nt":  # Windows
            python_path = os.path.join("venv", "Scripts", "python")
        else:  # Unix/MacOS
            python_path = os.path.join("venv", "bin", "python")

        # Activate virtual environment and run the application
        if os.name == "nt":  # Windows
            activate_script = os.path.join("venv", "Scripts", "activate")
            subprocess.run([python_path, "run.py"], check=True, env=dict(os.environ, PYTHONPATH=os.getcwd()))
        else:  # Unix/MacOS
            activate_script = os.path.join("venv", "bin", "activate")
            subprocess.run([python_path, "run.py"], check=True, env=dict(os.environ, PYTHONPATH=os.getcwd()))

    except subprocess.CalledProcessError as e:
        logger.error(f"Error running application: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
