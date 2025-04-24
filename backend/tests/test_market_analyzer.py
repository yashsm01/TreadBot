import pytest
import pandas as pd
import numpy as np
from ..analysis.market_analyzer import MarketAnalyzer
from ..trader.mock_exchange import MockExchange
from datetime import datetime, timedelta

@pytest.fixture
def market_analyzer():
    """Create a MarketAnalyzer instance with mock exchange"""
    exchange = MockExchange()
    analyzer = MarketAnalyzer(exchange)
    return analyzer

@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data for testing"""
    now = datetime.now()
    dates = [now - timedelta(minutes=i) for i in range(100)]
    data = {
        'timestamp': dates,
        'open': np.random.normal(50000, 1000, 100),
        'high': np.random.normal(51000, 1000, 100),
        'low': np.random.normal(49000, 1000, 100),
        'close': np.random.normal(50000, 1000, 100),
        'volume': np.random.normal(100, 10, 100)
    }
    return pd.DataFrame(data)

@pytest.mark.asyncio
async def test_initialization(market_analyzer):
    """Test market analyzer initialization"""
    await market_analyzer.initialize()
    assert market_analyzer.exchange is not None
    assert market_analyzer.timeframes == ["1m", "5m", "15m", "1h", "4h", "1d"]

@pytest.mark.asyncio
async def test_get_market_analysis(market_analyzer):
    """Test getting market analysis"""
    analysis = await market_analyzer.get_market_analysis("BTC/USDT", "5m")

    # Check structure
    assert "market_summary" in analysis
    assert "trading_signals" in analysis
    assert "volatility_metrics" in analysis

    # Check market summary
    summary = analysis["market_summary"]
    assert "last_price" in summary
    assert "price_change_24h" in summary
    assert "volume_24h" in summary

    # Check trading signals
    signals = analysis["trading_signals"]
    assert "trend" in signals
    assert "momentum" in signals
    assert "volume_ratio" in signals

    # Check volatility metrics
    volatility = analysis["volatility_metrics"]
    assert "volatility" in volatility
    assert "price_range" in volatility

@pytest.mark.asyncio
async def test_calculate_technical_indicators(market_analyzer, sample_ohlcv_data):
    """Test technical indicator calculations"""
    df = sample_ohlcv_data

    # Test RSI
    rsi = market_analyzer._calculate_rsi(df['close'])
    assert len(rsi) == len(df)
    assert all(0 <= x <= 100 for x in rsi.dropna())

    # Test MACD
    macd, signal = market_analyzer._calculate_macd(df['close'])
    assert len(macd) == len(df)
    assert len(signal) == len(df)

    # Test Bollinger Bands
    upper, middle, lower = market_analyzer._calculate_bollinger_bands(df['close'])
    assert len(upper) == len(df)
    assert len(middle) == len(df)
    assert len(lower) == len(df)
    assert all(upper >= middle)
    assert all(middle >= lower)

@pytest.mark.asyncio
async def test_trend_analysis(market_analyzer, sample_ohlcv_data):
    """Test trend analysis"""
    df = sample_ohlcv_data
    trend = market_analyzer._analyze_trend(df)

    assert isinstance(trend, str)
    assert trend in ["bullish", "bearish", "neutral"]

@pytest.mark.asyncio
async def test_volatility_analysis(market_analyzer, sample_ohlcv_data):
    """Test volatility analysis"""
    df = sample_ohlcv_data
    volatility = market_analyzer._calculate_volatility(df)

    assert isinstance(volatility, float)
    assert 0 <= volatility <= 1

@pytest.mark.asyncio
async def test_volume_analysis(market_analyzer, sample_ohlcv_data):
    """Test volume analysis"""
    df = sample_ohlcv_data
    volume_ratio = market_analyzer._analyze_volume(df)

    assert isinstance(volume_ratio, float)
    assert volume_ratio > 0

@pytest.mark.asyncio
async def test_support_resistance_levels(market_analyzer, sample_ohlcv_data):
    """Test support and resistance level calculation"""
    df = sample_ohlcv_data
    support, resistance = market_analyzer._calculate_support_resistance(df)

    assert isinstance(support, float)
    assert isinstance(resistance, float)
    assert support < resistance

@pytest.mark.asyncio
async def test_error_handling(market_analyzer):
    """Test error handling for invalid inputs"""
    # Test invalid symbol
    with pytest.raises(Exception):
        await market_analyzer.get_market_analysis("INVALID/PAIR", "5m")

    # Test invalid timeframe
    with pytest.raises(Exception):
        await market_analyzer.get_market_analysis("BTC/USDT", "invalid")

    # Test missing data
    with pytest.raises(Exception):
        await market_analyzer.get_market_analysis("", "5m")

if __name__ == "__main__":
    pytest.main(["-v", __file__])
