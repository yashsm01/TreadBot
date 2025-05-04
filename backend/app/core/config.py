from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Crypto Straddle Trading Bot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv('DEBUG', 'false').lower() == 'true'
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Trading Bot API"
    PROJECT_VERSION: str = "1.0.0"
    PROJECT_DESCRIPTION: str = "API for automated crypto trading using time-based straddling strategy"

    # Server Settings
    HOST: str = os.getenv('HOST', '0.0.0.0')
    PORT: int = int(os.getenv('PORT', 8000))

    # CORS Settings
    ALLOWED_ORIGINS: str = "*"

    # Database Settings
    DATABASE_URL: str = "postgresql://postgres:1234@localhost:5432/crypto_trading"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "1234"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "crypto_trading"

    # MongoDB (if needed)
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "crypto_trading")
    MONGODB_COLLECTION: str = os.getenv("MONGODB_COLLECTION", "strategy_logs")

    # Trading Settings
    PAPER_TRADING: bool = True
    TRADING_PAIRS: str = "BTC/USDT,ETH/USDT"
    DEFAULT_TRADING_PAIR: str = "BTC/USDT"
    MIN_TRADE_AMOUNT: float = 0.001
    MAX_TRADE_AMOUNT: float = 1.0
    TRADE_FEE: float = 0.001  # 0.1%

    # Telegram Settings
    TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN", "7816751552:AAEdH_pquW9QFyr_OghH3RxkDqtOTBT3LsQ")
    TELEGRAM_CHAT_ID: Optional[str] = os.getenv("TELEGRAM_CHAT_ID", "505504650")

    # Logging Settings
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT: str = os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # API Keys
    BINANCE_API_KEY: str = ""  # Add your API key here
    BINANCE_SECRET_KEY: str = ""  # Add your secret key here

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"  # Allow extra fields from env file

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
