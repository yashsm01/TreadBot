from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.crud.crud_user_portfolio_summary import user_portfolio_summary_crud
from app.core.logger import logger

router = APIRouter()


@router.get("/latest", response_model=Dict[str, Any])
async def get_latest_portfolio_summary(
    user_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get the latest portfolio summary
    """
    try:
        summary = await user_portfolio_summary_crud.get_latest_summary(
            db=db,
            user_id=user_id
        )

        if not summary:
            raise HTTPException(status_code=404, detail="No portfolio summary found")

        # Format response
        return {
            "id": summary.id,
            "timestamp": summary.timestamp,
            "total_value": summary.total_value,
            "total_cost_basis": summary.total_cost_basis,
            "total_profit_loss": summary.total_profit_loss,
            "total_profit_loss_percentage": summary.total_profit_loss_percentage,
            "crypto_value": summary.crypto_value,
            "stable_value": summary.stable_value,
            "daily_change": summary.daily_change,
            "weekly_change": summary.weekly_change,
            "monthly_change": summary.monthly_change,
            "assets": summary.assets,
            "trades_today": summary.trades_today,
            "swaps_today": summary.swaps_today,
            "market_trend": summary.market_trend,
            "market_volatility": summary.market_volatility,
            "is_hedged": summary.is_hedged,
            "risk_level": summary.risk_level
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting latest portfolio summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get portfolio summary: {str(e)}")


@router.get("/history", response_model=List[Dict[str, Any]])
async def get_portfolio_history(
    days: int = Query(7, ge=1, le=30),
    interval: str = Query("daily", regex="^(daily|hourly)$"),
    user_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get historical portfolio summaries for the specified time period
    """
    try:
        summaries = await user_portfolio_summary_crud.get_historical_summaries(
            db=db,
            user_id=user_id,
            days=days,
            interval=interval
        )

        if not summaries:
            raise HTTPException(status_code=404, detail="No portfolio history found")

        # Format response
        result = []
        for summary in summaries:
            result.append({
                "id": summary.id,
                "timestamp": summary.timestamp,
                "total_value": summary.total_value,
                "total_profit_loss": summary.total_profit_loss,
                "total_profit_loss_percentage": summary.total_profit_loss_percentage,
                "crypto_value": summary.crypto_value,
                "stable_value": summary.stable_value,
                "daily_change": summary.daily_change,
                "market_trend": summary.market_trend,
                "risk_level": summary.risk_level
            })

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting portfolio history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get portfolio history: {str(e)}")


@router.get("/assets", response_model=Dict[str, Any])
async def get_portfolio_assets(
    user_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed breakdown of assets in the portfolio from the latest summary
    """
    try:
        summary = await user_portfolio_summary_crud.get_latest_summary(
            db=db,
            user_id=user_id
        )

        if not summary:
            raise HTTPException(status_code=404, detail="No portfolio summary found")

        if not summary.assets:
            return {"assets": {}}

        # Return the assets JSON directly
        return {"assets": summary.assets}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting portfolio assets: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get portfolio assets: {str(e)}")
