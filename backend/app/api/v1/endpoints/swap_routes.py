from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Optional
from app.core.database import get_db
from app.services.oneinch_service import oneinch_service
from app.services.swap_service import swap_service
from app.core.config import settings
from app.core.logger import logger
from datetime import datetime

router = APIRouter()

@router.get("/quote", response_model=Dict)
async def get_swap_quote(
    from_symbol: str = Query(..., description="Source token symbol"),
    to_symbol: str = Query(..., description="Destination token symbol"),
    amount: float = Query(..., description="Amount to swap")
):
    """Get swap quote from 1inch"""
    try:
        quote = await swap_service.get_swap_quote(from_symbol, to_symbol, amount)
        return {
            "success": True,
            "data": quote,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting swap quote: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/execute", response_model=Dict)
async def execute_swap(
    from_symbol: str,
    to_symbol: str,
    amount: float,
    position_id: int,
    slippage: Optional[float] = None,
    db: AsyncSession = Depends(get_db)
):
    """Execute token swap"""
    try:
        # Set swap service database session
        swap_service.db = db

        if slippage is None:
            slippage = settings.DEFAULT_SLIPPAGE

        # Execute real swap if enabled, otherwise simulate
        if settings.SWAP_ENABLED:
            result = await swap_service.execute_real_swap(
                from_symbol=from_symbol,
                to_symbol=to_symbol,
                amount=amount,
                position_id=position_id
            )
        else:
            result = await swap_service.simulate_swap(
                from_symbol=from_symbol,
                to_symbol=to_symbol,
                amount=amount,
                position_id=position_id
            )

        return {
            "success": True,
            "data": result,
            "swap_mode": "REAL" if settings.SWAP_ENABLED else "SIMULATION",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error executing swap: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/allowance/{token_symbol}", response_model=Dict)
async def check_token_allowance(
    token_symbol: str,
    wallet_address: Optional[str] = None
):
    """Check token allowance for 1inch router"""
    try:
        if not settings.SWAP_ENABLED:
            return {
                "success": False,
                "message": "Swaps are disabled",
                "allowance": 0
            }

        token_address = oneinch_service.get_token_address(token_symbol)
        allowance = await oneinch_service.check_allowance(token_address, wallet_address)

        return {
            "success": True,
            "data": {
                "token_symbol": token_symbol,
                "token_address": token_address,
                "allowance": allowance,
                "wallet_address": wallet_address or oneinch_service.wallet_address
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error checking allowance: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/approve/{token_symbol}", response_model=Dict)
async def approve_token(
    token_symbol: str,
    amount: Optional[str] = None
):
    """Approve token for trading with 1inch router"""
    try:
        if not settings.SWAP_ENABLED:
            return {
                "success": False,
                "message": "Swaps are disabled"
            }

        token_address = oneinch_service.get_token_address(token_symbol)
        tx_hash = await oneinch_service.approve_token(token_address, amount)

        return {
            "success": True,
            "data": {
                "token_symbol": token_symbol,
                "token_address": token_address,
                "transaction_hash": tx_hash,
                "amount": amount,
                "status": "PENDING" if tx_hash != "sufficient_allowance" else "SUFFICIENT"
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error approving token: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tokens", response_model=Dict)
async def get_supported_tokens():
    """Get list of supported tokens"""
    try:
        return {
            "success": True,
            "data": {
                "supported_tokens": oneinch_service.token_addresses,
                "chain_id": oneinch_service.chain_id,
                "swap_enabled": settings.SWAP_ENABLED
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting supported tokens: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status", response_model=Dict)
async def get_swap_status():
    """Get swap service status and configuration"""
    try:
        return {
            "success": True,
            "data": {
                "swap_enabled": settings.SWAP_ENABLED,
                "chain_id": oneinch_service.chain_id,
                "default_slippage": settings.DEFAULT_SLIPPAGE,
                "wallet_address": oneinch_service.wallet_address,
                "api_configured": bool(oneinch_service.api_key),
                "web3_connected": oneinch_service.web3.is_connected() if hasattr(oneinch_service.web3, 'is_connected') else True
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting swap status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-connection", response_model=Dict)
async def test_oneinch_connection():
    """Test connection to 1inch API"""
    try:
        # Test with a simple quote request
        test_quote = await oneinch_service.get_quote(
            src_token=oneinch_service.get_token_address("USDT"),
            dst_token=oneinch_service.get_token_address("USDC"),
            amount="1000000000000000000"  # 1 USDT in wei
        )

        return {
            "success": True,
            "data": {
                "connection_status": "OK",
                "api_response": test_quote,
                "chain_id": oneinch_service.chain_id
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error testing 1inch connection: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/available-tokens", response_model=Dict)
async def get_available_tokens(db: AsyncSession = Depends(get_db)):
    """Get available tokens from 1inch API"""
    try:
        # Set swap service database session
        swap_service.db = db

        tokens = await swap_service.get_token()
        return {
            "success": True,
            "data": tokens,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting available tokens: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-simulation", response_model=Dict)
async def test_swap_simulation(
    from_symbol: str,
    to_symbol: str,
    amount: float,
    position_id: int = 1,
    db: AsyncSession = Depends(get_db)
):
    """Test swap simulation without real execution"""
    try:
        # Set swap service database session
        swap_service.db = db

        result = await swap_service.simulate_swap(
            from_symbol=from_symbol,
            to_symbol=to_symbol,
            amount=amount,
            position_id=position_id
        )

        return {
            "success": True,
            "data": result,
            "swap_mode": "SIMULATION",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error testing swap simulation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health-check", response_model=Dict)
async def comprehensive_health_check():
    """Comprehensive health check for 1inch integration"""
    try:
        health_status = {
            "overall_status": "OK",
            "timestamp": datetime.now().isoformat(),
            "configuration": {
                "api_key_configured": bool(oneinch_service.api_key),
                "wallet_configured": bool(oneinch_service.wallet_address),
                "private_key_configured": bool(oneinch_service.private_key),
                "web3_initialized": oneinch_service.web3 is not None,
                "is_fully_configured": oneinch_service.is_configured,
                "chain_id": oneinch_service.chain_id,
                "swap_enabled": settings.SWAP_ENABLED
            },
            "connectivity": {
                "web3_connected": False,
                "api_accessible": False
            },
            "supported_tokens": len(oneinch_service.token_addresses),
            "errors": []
        }

        # Test Web3 connection
        try:
            if oneinch_service.web3:
                latest_block = oneinch_service.web3.eth.block_number
                health_status["connectivity"]["web3_connected"] = True
                health_status["connectivity"]["latest_block"] = latest_block
        except Exception as e:
            health_status["errors"].append(f"Web3 connection failed: {str(e)}")

        # Test 1inch API accessibility (only if API key is configured)
        if oneinch_service.api_key:
            try:
                # Test with a simple quote request
                test_quote = await oneinch_service.get_quote(
                    src_token=oneinch_service.get_token_address("USDT"),
                    dst_token=oneinch_service.get_token_address("USDC"),
                    amount="1000000000000000000"  # 1 USDT in wei
                )
                health_status["connectivity"]["api_accessible"] = True
                health_status["connectivity"]["sample_quote"] = {
                    "from": "1 USDT",
                    "to": f"{float(test_quote.get('dstAmount', 0)) / 10**18:.6f} USDC"
                }
            except Exception as e:
                health_status["errors"].append(f"1inch API test failed: {str(e)}")
        else:
            health_status["errors"].append("1inch API key not configured")

        # Determine overall status
        if health_status["errors"]:
            health_status["overall_status"] = "DEGRADED" if health_status["connectivity"]["web3_connected"] else "ERROR"

        return {
            "success": True,
            "data": health_status
        }

    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/tokens/search")
async def search_tokens(
    query: str,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """Search for tokens by name or symbol"""
    try:
        oneinch_service.db = db
        results = oneinch_service.search_tokens(query, limit)
        return {
            "success": True,
            "query": query,
            "results": results,
            "total_found": len(results)
        }
    except Exception as e:
        logger.error(f"Error searching tokens: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tokens/popular")
async def get_popular_tokens(
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Get list of popular tokens"""
    try:
        oneinch_service.db = db
        popular_tokens = oneinch_service.get_popular_tokens(limit)
        return {
            "success": True,
            "popular_tokens": popular_tokens,
            "total": len(popular_tokens)
        }
    except Exception as e:
        logger.error(f"Error getting popular tokens: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tokens/info/{symbol}")
async def get_token_info(
    symbol: str,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information about a specific token"""
    try:
        oneinch_service.db = db
        token_info = oneinch_service.get_token_info(symbol)

        if "error" in token_info:
            raise HTTPException(status_code=404, detail=token_info["error"])

        return {
            "success": True,
            "token_info": token_info
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting token info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tokens/cache/info")
async def get_cache_info(
    db: AsyncSession = Depends(get_db)
):
    """Get information about the token cache"""
    try:
        oneinch_service.db = db
        cache_info = oneinch_service.get_cache_info()
        return {
            "success": True,
            "cache_info": cache_info
        }
    except Exception as e:
        logger.error(f"Error getting cache info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tokens/cache/refresh")
async def refresh_token_cache(
    db: AsyncSession = Depends(get_db)
):
    """Manually refresh the token cache from 1inch API"""
    try:
        oneinch_service.db = db
        total_tokens = oneinch_service.refresh_token_addresses()
        return {
            "success": True,
            "message": "Token cache refreshed successfully",
            "total_tokens": total_tokens
        }
    except Exception as e:
        logger.error(f"Error refreshing token cache: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tokens/all")
async def get_all_tokens(
    page: int = 1,
    per_page: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Get all available tokens with pagination"""
    try:
        oneinch_service.db = db
        all_tokens = []
        for symbol, address in oneinch_service.token_addresses.items():
            all_tokens.append({
                "symbol": symbol,
                "address": address
            })

        # Sort by symbol
        all_tokens.sort(key=lambda x: x["symbol"])

        # Pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_tokens = all_tokens[start_idx:end_idx]

        return {
            "success": True,
            "tokens": paginated_tokens,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_tokens": len(all_tokens),
                "total_pages": (len(all_tokens) + per_page - 1) // per_page,
                "has_next": end_idx < len(all_tokens),
                "has_prev": page > 1
            }
        }
    except Exception as e:
        logger.error(f"Error getting all tokens: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
