from pydantic_settings import BaseSettings
from typing import List
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
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "1234")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "crypto_trading")

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # MongoDB (if needed)
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "crypto_trading")
    MONGODB_COLLECTION: str = os.getenv("MONGODB_COLLECTION", "strategy_logs")

    # Trading Settings
    PAPER_TRADING: bool = True
    TRADING_PAIRS: str = "BTC/USDT,ETH/USDT"
    DEFAULT_TRADING_PAIR: str = "BTC/USDT"
    DEFAULT_QUANTITY: float = float(os.getenv("DEFAULT_QUANTITY", "0.001"))
    DEFAULT_TP_PCT: float = float(os.getenv("DEFAULT_TP_PCT", "1.0"))
    DEFAULT_SL_PCT: float = float(os.getenv("DEFAULT_SL_PCT", "0.5"))

    # Telegram Settings
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "7816751552:AAEdH_pquW9QFyr_OghH3RxkDqtOTBT3LsQ")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "505504650")

    # Logging Settings
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT: str = os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # API Keys
    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET: str = os.getenv("BINANCE_API_SECRET", "")

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"  # Allow extra fields from env file

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
