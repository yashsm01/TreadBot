from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    APP_NAME: str = "Crypto Straddle Trading Bot"
    VERSION: str = "1.0.0"
    APP_VERSION: str = VERSION
    APP_DESCRIPTION: str = "API for automated crypto trading using time-based straddling strategy"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    TESTING: bool = True
    SWAP_FEE_PERCENTAGE: float = 0.001

    # Database settings
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "1234"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "crypto_trading"

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Get database URL with async driver."""
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def DATABASE_URL(self) -> str:
        """Get database URL with sync driver for alembic."""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Stable coins
    STABLE_COINS: List[str] = ["USDT", "USDC", "BUSD", "DAI", "TUSD"]

    # Trading settings
    DEFAULT_TP_PCT: float = 0.8  # 2% take profit
    DEFAULT_SL_PCT: float = 0.3  # 1% stop loss
    DEFAULT_INTERVAL: str = "5m"
    DEFAULT_BREAKOUT_PCT: float = 0.5
    DEFAULT_QUANTITY: float = 0.001

    # 5m_LIMIT
    TREADING_DEFAULT_LIMIT: int = 20
    TREADING_DEFAULT_INTERVAL: str = "5m"

    # Telegram Settings
    TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN", "7816751552:AAEdH_pquW9QFyr_OghH3RxkDqtOTBT3LsQ")
    TELEGRAM_CHAT_ID: Optional[str] = os.getenv("TELEGRAM_CHAT_ID", "505504650")

    # MongoDB settings (if needed)
    MONGODB_URL: str = "mongodb://localhost:27017"

    # Server Settings
    HOST: str = os.getenv('HOST', '0.0.0.0')
    PORT: int = int(os.getenv('PORT', 8000))

    # CORS Settings
    ALLOWED_ORIGINS: str = "*"

    # Trading Settings
    PAPER_TRADING: bool = True
    TRADING_PAIRS: str = "BTC/USDT,ETH/USDT"
    DEFAULT_TRADING_PAIR: str = "BTC/USDT"
    MIN_TRADE_AMOUNT: float = 0.001
    MAX_TRADE_AMOUNT: float = 1.0
    TRADE_FEE: float = 0.001  # 0.1%

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
