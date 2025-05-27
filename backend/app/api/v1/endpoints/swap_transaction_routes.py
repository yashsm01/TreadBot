from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.swap_service import swap_service
from app.crud.crud_swap_transaction import swap_transaction_crud
from app.core.logger import logger
from pydantic import BaseModel, Field
from datetime import datetime

router = APIRouter()

class SwapToStableCoinRequest(BaseModel):
    symbol: str = Field(..., description="Cryptocurrency symbol to swap (e.g., 'BTC')")
    quantity: float = Field(..., gt=0, description="Amount to swap")
    current_price: Optional[float] = Field(None, description="Current price (optional, will be fetched if not provided)")
    position_id: int = Field(None,description="position id (optional, will be fetched if not provided)")

class SwapFromStableCoinRequest(BaseModel):
    stable_coin: str = Field(..., description="Stablecoin symbol (e.g., 'USDT')")
    symbol: str = Field(..., description="Cryptocurrency symbol to buy (e.g., 'BTC')")
    amount: float = Field(..., gt=0, description="Amount of stablecoin to swap")
    position_id: int = Field(None,description="position id (optional, will be fetched if not provided)")

@router.post("/to-stable", response_model=Dict[str, Any])
async def swap_to_stable_coin(
    request: SwapToStableCoinRequest = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Swap a cryptocurrency for the best available stablecoin
    """
    try:
        # Set DB session in case it's not set
        swap_service.db = db

        result = await swap_service.swap_symbol_stable_coin(
            symbol=request.symbol,
            quantity=request.quantity,
            current_price=request.current_price,
            position_id=request.position_id
        )

        if result["status"] == "error" or result["status"] == "failed":
            raise HTTPException(status_code=400, detail=result["message"])

        return result
    except Exception as e:
        logger.error(f"Error swapping to stablecoin: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to perform swap: {str(e)}")

@router.post("/from-stable", response_model=Dict[str, Any])
async def swap_from_stable_coin(
    request: SwapFromStableCoinRequest = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Swap from a stablecoin to a cryptocurrency
    """
    try:
        # Set DB session in case it's not set
        swap_service.db = db

        result = await swap_service.swap_stable_coin_symbol(
            stable_coin=request.stable_coin,
            symbol=request.symbol,
            amount=request.amount,
            position_id=request.position_id
        )

        if result["status"] == "error" or result["status"] == "failed":
            raise HTTPException(status_code=400, detail=result["message"])

        return result
    except Exception as e:
        logger.error(f"Error swapping from stablecoin: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to perform swap: {str(e)}")

@router.get("/history", response_model=List[Dict[str, Any]])
async def get_swap_transaction_history(
    limit: int = 10,
    offset: int = 0,
    symbol: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get swap transaction history with optional filtering by symbol
    """
    try:
        filters = {}
        if symbol:
            # Filter by either from_symbol or to_symbol
            filters = {
                "or_": {
                    "from_symbol": symbol.upper(),
                    "to_symbol": symbol.upper()
                }
            }

        transactions = await swap_transaction_crud.get_multi(
            db,
            skip=offset,
            limit=limit,
            filters=filters
        )

        result = []
        for tx in transactions:
            result.append({
                "transaction_id": tx.transaction_id,
                "from_symbol": tx.from_symbol,
                "to_symbol": tx.to_symbol,
                "from_amount": tx.from_amount,
                "to_amount": tx.to_amount,
                "rate": tx.rate,
                "fee_percentage": tx.fee_percentage,
                "fee_amount": tx.fee_amount,
                "timestamp": tx.timestamp,
                "status": tx.status,
                "user_id": tx.user_id
            })

        return result
    except Exception as e:
        logger.error(f"Error getting swap transaction history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get swap transaction history: {str(e)}")

@router.get("/{transaction_id}", response_model=Dict[str, Any])
async def get_swap_transaction(
    transaction_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get details of a specific swap transaction
    """
    try:
        transaction = await swap_transaction_crud.get_by_transaction_id(db, transaction_id=transaction_id)

        if not transaction:
            raise HTTPException(status_code=404, detail="Swap transaction not found")

        return {
            "transaction_id": transaction.transaction_id,
            "from_symbol": transaction.from_symbol,
            "to_symbol": transaction.to_symbol,
            "from_amount": transaction.from_amount,
            "to_amount": transaction.to_amount,
            "rate": transaction.rate,
            "fee_percentage": transaction.fee_percentage,
            "fee_amount": transaction.fee_amount,
            "timestamp": transaction.timestamp,
            "status": transaction.status,
            "user_id": transaction.user_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting swap transaction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get swap transaction: {str(e)}")

@router.get("/profit-summary", response_model=Dict)
async def get_swap_profit_summary(
    user_id: Optional[int] = None,
    symbol: Optional[str] = None,
    days: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get profit/loss summary for swap transactions with optional filters
    """
    try:
        summary = await swap_transaction_crud.get_profit_summary(
            db, user_id=user_id, symbol=symbol, days=days
        )
        return {
            "status": "success",
            "data": summary
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get swap profit summary: {str(e)}"
        )

@router.get("/symbol-performance", response_model=Dict)
async def get_symbol_performance(
    user_id: Optional[int] = None,
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """
    Get performance breakdown by symbol for swap transactions
    """
    try:
        performance = await swap_transaction_crud.get_symbol_performance(
            db, user_id=user_id, days=days
        )
        return {
            "status": "success",
            "data": performance
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get symbol performance: {str(e)}"
        )

@router.get("/profit-loss-report")
async def get_profit_loss_report(
    user_id: int = 1,
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive profit/loss report combining portfolio and swap data
    """
    try:
        # Get swap P/L summary
        swap_summary = await swap_transaction_crud.get_profit_summary(
            db, user_id=user_id, days=days
        )

        # Get symbol performance
        symbol_performance = await swap_transaction_crud.get_symbol_performance(
            db, user_id=user_id, days=days
        )

        # Get portfolio summary
        from app.crud.crud_portfolio import portfolio_crud
        portfolio_summary = await portfolio_crud.get_portfolio_with_profit_summary(
            db, user_id=user_id
        )

        return {
            "status": "success",
            "data": {
                "report_period_days": days,
                "swap_transactions": swap_summary,
                "symbol_performance": symbol_performance,
                "portfolio_summary": portfolio_summary,
                "generated_at": datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate P/L report: {str(e)}"
        )
