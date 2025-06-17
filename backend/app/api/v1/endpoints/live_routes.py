from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from app.services.live_service import live_service
from app.core.logger import logger
from datetime import datetime

router = APIRouter()

@router.get("/tokens", response_model=List[Dict[str, Any]])
async def get_live_tokens(
    symbols: Optional[str] = Query(None, description="Comma-separated list of token symbols (e.g., 'BTCUSDT,ETHUSDT')")
):
    """
    Get live token data formatted similar to mock tokens

    Returns real-time data for popular cryptocurrencies including:
    - Current price
    - 24h change percentage
    - Volume
    - Market cap (estimated)
    - High/Low 24h
    - Volatility
    """
    try:
        # Parse symbols if provided
        symbol_list = None
        if symbols:
            symbol_list = [s.strip().upper() for s in symbols.split(",")]
            # Ensure symbols end with USDT if they don't have a quote currency
            symbol_list = [
                s if s.endswith(("USDT", "USDC", "BUSD")) else f"{s}USDT"
                for s in symbol_list
            ]

        tokens = await live_service.get_live_tokens(symbol_list)

        if not tokens:
            logger.warning("No token data available")
            return []

        logger.info(f"Successfully fetched {len(tokens)} tokens")
        return tokens

    except Exception as e:
        logger.error(f"Error fetching live tokens: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch token data: {str(e)}")

@router.get("/signals", response_model=List[Dict[str, Any]])
async def get_live_signals(
    symbols: Optional[str] = Query(None, description="Comma-separated list of token symbols for signal analysis"),
    limit: int = Query(5, description="Maximum number of signals to return")
):
    """
    Generate trading signals based on real market data

    Returns trading signals with:
    - Signal type (LONG/SHORT)
    - Entry price
    - Stop loss
    - Take profit
    - Confidence level
    - Market momentum analysis
    """
    try:
        # Parse symbols if provided
        symbol_list = None
        if symbols:
            symbol_list = [s.strip().upper() for s in symbols.split(",")]
            # Ensure symbols end with USDT if they don't have a quote currency
            symbol_list = [
                s if s.endswith(("USDT", "USDC", "BUSD")) else f"{s}USDT"
                for s in symbol_list
            ]
            # Limit the number of symbols for performance
            symbol_list = symbol_list[:limit]

        signals = await live_service.get_live_signals(symbol_list)

        # Limit results
        signals = signals[:limit]

        logger.info(f"Generated {len(signals)} trading signals")
        return signals

    except Exception as e:
        logger.error(f"Error generating live signals: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate signals: {str(e)}")

@router.get("/token/{symbol}", response_model=Dict[str, Any])
async def get_token_details(symbol: str):
    """
    Get detailed information for a specific token

    Returns comprehensive data including:
    - Current price and bid/ask
    - 24h statistics
    - Short-term price changes
    - Price history
    - Volatility metrics
    """
    try:
        token_details = await live_service.get_token_details(symbol.upper())

        if token_details.get("error"):
            raise HTTPException(status_code=404, detail=token_details["error"])

        logger.info(f"Fetched details for token: {symbol}")
        return token_details

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching token details for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch token details: {str(e)}")

@router.get("/market-overview", response_model=Dict[str, Any])
async def get_market_overview():
    """
    Get comprehensive market overview including tokens and signals

    Returns:
    - Top tokens with live data
    - Active trading signals
    - Market summary statistics
    """
    try:
        # Fetch both tokens and signals concurrently
        import asyncio

        tokens_task = live_service.get_live_tokens()
        signals_task = live_service.get_live_signals()

        tokens, signals = await asyncio.gather(tokens_task, signals_task)

        # Calculate market summary
        total_volume = sum(token.get("volume", 0) for token in tokens)
        avg_change = sum(token.get("change24h", 0) for token in tokens) / len(tokens) if tokens else 0

        # Count positive and negative performers
        positive_count = sum(1 for token in tokens if token.get("change24h", 0) > 0)
        negative_count = len(tokens) - positive_count

        market_summary = {
            "totalTokens": len(tokens),
            "totalVolume": int(total_volume),
            "averageChange24h": round(avg_change, 2),
            "positivePerformers": positive_count,
            "negativePerformers": negative_count,
            "activeSignals": len(signals),
            "timestamp": int(datetime.now().timestamp() * 1000)
        }

        return {
            "tokens": tokens[:10],  # Top 10 tokens
            "signals": signals[:5],  # Top 5 signals
            "marketSummary": market_summary,
            "status": "success",
            "timestamp": int(datetime.now().timestamp() * 1000)
        }

    except Exception as e:
        logger.error(f"Error fetching market overview: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch market overview: {str(e)}")

@router.get("/popular-tokens", response_model=List[Dict[str, Any]])
async def get_popular_tokens(limit: int = Query(10, description="Number of tokens to return")):
    """
    Get popular tokens sorted by volume and market activity
    """
    try:
        # Get default popular tokens
        popular_symbols = [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "DOTUSDT",
            "LINKUSDT", "MATICUSDT", "AVAXUSDT", "DOGEUSDT", "BNBUSDT"
        ]

        tokens = await live_service.get_live_tokens(popular_symbols[:limit])

        # Sort by volume (highest first)
        tokens.sort(key=lambda x: x.get("volume", 0), reverse=True)

        return tokens[:limit]

    except Exception as e:
        logger.error(f"Error fetching popular tokens: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch popular tokens: {str(e)}")

@router.get("/trending", response_model=List[Dict[str, Any]])
async def get_trending_tokens(limit: int = Query(5, description="Number of trending tokens to return")):
    """
    Get trending tokens based on price movement and volatility
    """
    try:
        # Get a broader set of tokens for analysis
        tokens = await live_service.get_live_tokens()

        if not tokens:
            return []

        # Sort by absolute price change percentage (most volatile first)
        tokens.sort(key=lambda x: abs(x.get("change24h", 0)), reverse=True)

        # Return top trending tokens
        trending = tokens[:limit]

        # Add trending score
        for token in trending:
            change = abs(token.get("change24h", 0))
            volatility = token.get("volatility", 0)
            volume = token.get("volume", 0)

            # Simple trending score calculation
            trending_score = (change * 0.4) + (volatility * 0.3) + (volume / 1000000 * 0.3)
            token["trendingScore"] = round(trending_score, 2)

        return trending

    except Exception as e:
        logger.error(f"Error fetching trending tokens: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch trending tokens: {str(e)}")

@router.get("/health", response_model=Dict[str, Any])
async def health_check():
    """
    Health check endpoint for the live data service
    """
    try:
        # Test fetching one token to verify service health
        test_token = await live_service.get_token_details("BTCUSDT")

        is_healthy = not test_token.get("error")

        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "service": "live_data_service",
            "timestamp": int(datetime.now().timestamp() * 1000),
            "binance_connection": is_healthy,
            "last_test": test_token.get("timestamp") if is_healthy else None
        }

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "service": "live_data_service",
            "error": str(e),
            "timestamp": int(datetime.now().timestamp() * 1000)
        }
