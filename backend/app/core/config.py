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
    STRATEGY: str = "SHORT" # LONG, MEDIUM, SHORT
    @property
    def DEFAULT_TP_PCT(self) -> float:
        STRATEGY_VALUE = {
            "LONG": 6.0,
            "MEDIUM": 3.0,
            "SHORT": 0.8
        }
        return STRATEGY_VALUE[self.STRATEGY]

    @property
    def DEFAULT_SL_PCT(self) -> float:
        STRATEGY_VALUE = {
            "LONG": 4.0,
            "MEDIUM": 2.0,
            "SHORT": 0.5
        }
        return STRATEGY_VALUE[self.STRATEGY]

    DEFAULT_INTERVAL: str = "5m"
    DEFAULT_BREAKOUT_PCT: float = 0.5
    DEFAULT_QUANTITY: float = 0.001

    # 5m_LIMIT
    TREADING_DEFAULT_LIMIT: int = 24
    TREADING_DEFAULT_INTERVAL: str = "1h"

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

    # 1inch API Configuration
    ONEINCH_API_KEY: str = "5udQ29Up3xGdnF4LNA2EDLm3QjKovqD3"
    # ONEINCH_CHAIN_ID: int = 56  # BSC by default
    ONEINCH_CHAIN_ID: int = 137 # Polygon
    # WEB3_RPC_URL: str = "https://bsc-dataseed.binance.org"
    WEB3_RPC_URL: str = "https://polygon-rpc.com"

    WALLET_ADDRESS: str = "0x3b8ecE3395c6e44A29835eea0074736aE861F8fe"  # Updated to user's Trust Wallet address
    PRIVATE_KEY: str = "0x0000000000000000000000000000000000000000000000000000000000000000"  # You need to add your private key here

    # Swap Configuration
    DEFAULT_SLIPPAGE: float = 1.0  # 1% slippage
    SWAP_ENABLED: bool = True  # Enable/disable actual swaps

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"  # Allow extra fields from env file

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
