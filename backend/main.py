from fastapi import FastAPI, HTTPException, Depends, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel
from typing import List, Optional, Dict
from dotenv import load_dotenv
import os
import logging
from sqlalchemy.orm import Session
from .trader.exchange_manager import ExchangeManager
from .trader.mock_exchange import MockExchange
from .services.telegram import TelegramService
from .services.scheduler import TradingScheduler
from .db.models import Trade, Config, TradeStatus, TradeType
from .api.trading import TradingAPI
from .analysis.market_analyzer import MarketAnalyzer
from datetime import datetime
import asyncio
from .database import get_db, SessionLocal, init_db, check_db_connection
from .services.portfolio import PortfolioService

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format=os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Crypto Straddle Trading Bot",
    description="API for automated crypto trading using time-based straddling strategy",
    version="1.0.0",
    docs_url=None,  # Disable default docs
    redoc_url=None  # Disable default redoc
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv('ALLOWED_ORIGINS', '*').split(','),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service instances (will be initialized during startup)
exchange_manager = None
market_analyzer = None
portfolio_service = None
telegram_service = None
trading_scheduler = None

# Pydantic models for API requests/responses
class TradeResponse(BaseModel):
    id: int
    coin: str
    entry_price: float
    exit_price: Optional[float]
    profit_pct: Optional[float]
    quantity: float
    status: str
    type: str
    created_at: str
    updated_at: Optional[str]

class ConfigResponse(BaseModel):
    id: int
    coin: str
    interval: str
    breakout_pct: float
    tp_pct: float
    sl_pct: float
    quantity: float
    created_at: str
    updated_at: Optional[str]

class ConfigUpdate(BaseModel):
    interval: Optional[str]
    breakout_pct: Optional[float]
    tp_pct: Optional[float]
    sl_pct: Optional[float]
    quantity: Optional[float]

class ManualTradeRequest(BaseModel):
    symbol: str
    quantity: float
    breakout_pct: float
    tp_pct: float
    sl_pct: float

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global exchange_manager, market_analyzer, portfolio_service, telegram_service, trading_scheduler

    try:
        # Check database connection
        if not check_db_connection():
            raise Exception("Could not connect to database")

        # Initialize database
        init_db()
        logger.info("Database initialized successfully")

        # Get database session
        db = SessionLocal()

        try:
            # Initialize exchange
            try:
                exchange_manager = ExchangeManager(db)
                logger.info("Real exchange connection established")
            except Exception as e:
                logger.warning(f"Real exchange not available, using mock exchange: {str(e)}")
                exchange_manager = MockExchange()
                logger.info("Mock exchange initialized")

            # Initialize market analyzer
            market_analyzer = MarketAnalyzer(exchange_manager)
            await market_analyzer.initialize()

            # Initialize portfolio service
            portfolio_service = PortfolioService(db, exchange_manager)

            # Initialize Telegram service
            telegram_service = TelegramService(market_analyzer, portfolio_service)
            await telegram_service.initialize()

            # Initialize trading scheduler
            trading_scheduler = TradingScheduler(telegram_service)
            trading_scheduler.start()

            logger.info("All services initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing services: {str(e)}")
            raise
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    try:
        if trading_scheduler:
            trading_scheduler.stop()
            logger.info("Trading scheduler stopped")

        if telegram_service:
            await telegram_service.stop()
            logger.info("Telegram service stopped")

        logger.info("All services shut down successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")

# Custom Swagger UI endpoint
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Crypto Straddle Trading Bot - API Documentation",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui.css",
    )

# OpenAPI schema endpoint
@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_endpoint():
    return get_openapi(
        title="Crypto Straddle Trading Bot",
        version="1.0.0",
        description="API for automated crypto trading using time-based straddling strategy",
        routes=app.routes,
    )

# Health check endpoint
@app.get("/status", response_model=Dict)
async def health_check():
    """Get the current status of the trading bot"""
    if not exchange_manager:
        raise HTTPException(status_code=503, detail="Services not initialized")

    return {
        "status": "healthy",
        "version": "1.0.0",
        "exchange_type": "mock" if isinstance(exchange_manager, MockExchange) else "real",
        "paper_trading": os.getenv('PAPER_TRADING', 'true').lower() == 'true',
        "trading_pairs": os.getenv('TRADING_PAIRS', '').split(','),
        "default_pair": os.getenv('DEFAULT_TRADING_PAIR', 'BTC/USDT')
    }

# Get all trades
@app.get("/trades", response_model=List[Dict])
async def get_trades(
    status: Optional[TradeStatus] = Query(None, description="Filter trades by status"),
    coin: Optional[str] = Query(None, description="Filter trades by coin"),
    limit: int = Query(100, description="Number of trades to return"),
    db: Session = Depends(get_db)
):
    """
    Get a list of all trades.

    Parameters:
        status: Filter trades by status (open, closed, cancelled)
        coin: Filter trades by coin (e.g., BTC/USDT)
        limit: Maximum number of trades to return

    Returns:
        List[Dict]: List of trades matching the criteria
    """
    trading_api = TradingAPI(db, exchange_manager, telegram_service)
    trades = await trading_api.get_trades(status, coin, limit)
    return [trade.__dict__ for trade in trades]

# Get profit summary
@app.get("/trades/profit-summary", response_model=Dict)
async def get_profit_summary(
    period: str = Query("daily", description="Summary period (daily, weekly, monthly)"),
    db: Session = Depends(get_db)
):
    """
    Get profit/loss summary for trades.

    Parameters:
        period: Summary period (daily, weekly, monthly)

    Returns:
        Dict: Profit/loss summary including total trades, winning trades, and net profit
    """
    trading_api = TradingAPI(db, exchange_manager, telegram_service)
    return await trading_api.get_profit_summary(period)

# Get current configuration
@app.get("/config", response_model=List[Dict])
async def get_config(
    coin: Optional[str] = Query(None, description="Filter config by coin"),
    db: Session = Depends(get_db)
):
    """
    Get current trading configuration.

    Parameters:
        coin: Filter config by coin (e.g., BTC/USDT)

    Returns:
        List[Dict]: List of trading configurations
    """
    trading_api = TradingAPI(db, exchange_manager, telegram_service)
    configs = await trading_api.get_config(coin)
    return [config.__dict__ for config in configs]

# Update configuration
@app.post("/config/update", response_model=Dict)
async def update_config(
    coin: str = Query(..., description="Trading pair to update"),
    config: Dict = Body(..., description="New configuration values"),
    db: Session = Depends(get_db)
):
    """
    Update trading configuration for a specific coin.

    Parameters:
        coin: Trading pair to update (e.g., BTC/USDT)
        config: New configuration values

    Returns:
        Dict: Updated configuration
    """
    trading_api = TradingAPI(db, exchange_manager, telegram_service)
    updated_config = await trading_api.update_config(coin, config)
    return updated_config.__dict__

# Trigger manual trade
@app.post("/trade/manual", response_model=Dict)
async def manual_trade(
    trade: Dict = Body(..., description="Trade parameters"),
    db: Session = Depends(get_db)
):
    """
    Trigger a manual straddle trade.

    Parameters:
        trade: Trade parameters including symbol, quantity, and percentages

    Returns:
        Dict: Created trade information
    """
    trading_api = TradingAPI(db, exchange_manager, telegram_service)
    created_trade = await trading_api.manual_trade(trade)
    return created_trade.__dict__

# Test Telegram notifications
@app.post("/test/telegram", response_model=Dict)
async def test_telegram_notifications(
    notification_type: str = Query(..., description="Type of notification to test (trade, error, summary, test)"),
    db: Session = Depends(get_db)
):
    """
    Test different types of Telegram notifications.

    Parameters:
        notification_type: Type of notification to test (trade, error, summary, test)

    Returns:
        Dict: Test result
    """
    # Define valid notification types
    valid_types = ["trade", "error", "summary", "test"]

    try:
        # Validate notification type
        if notification_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid notification type. Must be one of: {', '.join(valid_types)}"
            )

        # Check if Telegram is configured
        if not telegram_service.bot or not telegram_service.chat_id:
            raise HTTPException(
                status_code=500,
                detail="Telegram bot not configured. Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env file"
            )

        if notification_type == "trade":
            # Create a test trade using the actual exchange
            trading_api = TradingAPI(db, exchange_manager, telegram_service)
            await trading_api.manual_trade({
                "symbol": "BTC/USDT",
                "quantity": 0.001,
                "breakout_pct": 0.5,
                "tp_pct": 1.0,
                "sl_pct": 0.5
            })
        elif notification_type == "error":
            await telegram_service.send_error_notification(
                "Test error message",
                {
                    "Error Type": "Test Error",
                    "Component": "Test Component",
                    "Additional Info": "This is a test error notification"
                }
            )
        elif notification_type == "summary":
            await telegram_service.send_daily_summary({
                "total_trades": 10,
                "winning_trades": 6,
                "losing_trades": 4,
                "net_profit": 2.5,
                "best_trade": 1.5,
                "worst_trade": -0.8,
                "trades": [
                    {
                        "symbol": "BTC/USDT",
                        "profit_pct": 1.5,
                        "entry_price": 50000.0,
                        "exit_price": 50750.0
                    },
                    {
                        "symbol": "ETH/USDT",
                        "profit_pct": -0.8,
                        "entry_price": 3000.0,
                        "exit_price": 2976.0
                    }
                ]
            })
        elif notification_type == "test":
            success = await telegram_service.send_test_notification()
            if not success:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to send test notification. Please check your Telegram bot configuration."
                )

        return {
            "status": "success",
            "message": f"Successfully sent {notification_type} notification",
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise he
    except Exception as e:
        logger.error(f"Error testing Telegram notification: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error sending notification: {str(e)}"
        )

# Get market analysis
@app.get("/analysis/market", response_model=Dict)
async def get_market_analysis(
    symbol: str = Query(..., description="Trading pair to analyze (e.g., BTC/USDT)"),
    timeframe: str = Query("5m", description="Analysis timeframe (5m, 10m, 15m)")
):
    """
    Get comprehensive market analysis for manual trading decisions.

    Parameters:
        symbol: Trading pair to analyze (e.g., BTC/USDT)
        timeframe: Analysis timeframe (5m, 10m, 15m)

    Returns:
        Dict: Market analysis including indicators, signals, and recommendations
    """
    try:
        if symbol not in market_analyzer.supported_pairs:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported trading pair. Supported pairs: {', '.join(market_analyzer.supported_pairs)}"
            )

        if timeframe not in market_analyzer.timeframes:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported timeframe. Supported timeframes: {', '.join(market_analyzer.timeframes)}"
            )

        analysis = await market_analyzer.get_market_analysis(symbol, timeframe)
        return analysis
    except Exception as e:
        logger.error(f"Error getting market analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Get analysis for all supported pairs
@app.get("/analysis/market/all", response_model=Dict)
async def get_all_market_analysis(
    timeframe: str = Query("5m", description="Analysis timeframe (5m, 10m, 15m)")
):
    """
    Get market analysis for all supported trading pairs.

    Parameters:
        timeframe: Analysis timeframe (5m, 10m, 15m)

    Returns:
        Dict: Market analysis for all supported pairs
    """
    try:
        if timeframe not in market_analyzer.timeframes:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported timeframe. Supported timeframes: {', '.join(market_analyzer.timeframes)}"
            )

        analysis = {}
        for symbol in market_analyzer.supported_pairs:
            analysis[symbol] = await market_analyzer.get_market_analysis(symbol, timeframe)

        return {
            "timestamp": datetime.now().isoformat(),
            "timeframe": timeframe,
            "analysis": analysis
        }
    except Exception as e:
        logger.error(f"Error getting all market analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Start server with configuration from environment variables
    uvicorn.run(
        app,
        host=os.getenv('HOST', '0.0.0.0'),
        port=int(os.getenv('PORT', 8000)),
        debug=os.getenv('DEBUG', 'false').lower() == 'true'
    )
