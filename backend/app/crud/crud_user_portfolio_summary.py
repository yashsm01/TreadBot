from typing import Dict, List, Optional, Union, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, func
from datetime import datetime, timedelta
import json

from app.core.logger import logger
from app.models.user_portfolio_summary import UserPortfolioSummary
from app.crud.base import CRUDBase


class CRUDUserPortfolioSummary(CRUDBase[UserPortfolioSummary, Dict[str, Any], Dict[str, Any]]):
    async def create_summary(
        self,
        db: AsyncSession,
        *,
        user_id: Optional[int] = None,
        total_value: float,
        total_cost_basis: float,
        total_profit_loss: float,
        assets: Dict[str, Any],
        crypto_value: Optional[float] = 0.0,
        stable_value: Optional[float] = 0.0,
        market_trend: Optional[str] = None,
        market_volatility: Optional[float] = None,
        trades_today: Optional[int] = 0,
        swaps_today: Optional[int] = 0
    ) -> UserPortfolioSummary:
        """
        Create a new portfolio summary entry
        """
        try:
            # Calculate profit/loss percentage
            profit_loss_percentage = 0.0
            if total_cost_basis > 0:
                profit_loss_percentage = (total_profit_loss / total_cost_basis) * 100

            # Get previous summary to calculate daily/weekly changes
            daily_change = None
            weekly_change = None
            monthly_change = None

            one_day_ago = datetime.utcnow() - timedelta(days=1)
            one_week_ago = datetime.utcnow() - timedelta(days=7)
            one_month_ago = datetime.utcnow() - timedelta(days=30)

            # Get previous summary from 1 day ago
            prev_day_result = await db.execute(
                select(UserPortfolioSummary)
                .filter(UserPortfolioSummary.user_id == user_id)
                .filter(UserPortfolioSummary.timestamp > one_day_ago)
                .order_by(UserPortfolioSummary.timestamp.asc())
                .limit(1)
            )
            prev_day_summary = prev_day_result.scalars().first()

            if prev_day_summary:
                daily_change = ((total_value - prev_day_summary.total_value) / prev_day_summary.total_value) * 100 if prev_day_summary.total_value > 0 else 0.0

            # Get previous summary from 1 week ago
            prev_week_result = await db.execute(
                select(UserPortfolioSummary)
                .filter(UserPortfolioSummary.user_id == user_id)
                .filter(UserPortfolioSummary.timestamp > one_week_ago)
                .filter(UserPortfolioSummary.timestamp < one_week_ago + timedelta(days=1))
                .order_by(UserPortfolioSummary.timestamp.asc())
                .limit(1)
            )
            prev_week_summary = prev_week_result.scalars().first()

            if prev_week_summary:
                weekly_change = ((total_value - prev_week_summary.total_value) / prev_week_summary.total_value) * 100 if prev_week_summary.total_value > 0 else 0.0

            # Get previous summary from 1 month ago
            prev_month_result = await db.execute(
                select(UserPortfolioSummary)
                .filter(UserPortfolioSummary.user_id == user_id)
                .filter(UserPortfolioSummary.timestamp > one_month_ago)
                .filter(UserPortfolioSummary.timestamp < one_month_ago + timedelta(days=1))
                .order_by(UserPortfolioSummary.timestamp.asc())
                .limit(1)
            )
            prev_month_summary = prev_month_result.scalars().first()

            if prev_month_summary:
                monthly_change = ((total_value - prev_month_summary.total_value) / prev_month_summary.total_value) * 100 if prev_month_summary.total_value > 0 else 0.0

            # Determine if portfolio is hedged
            is_hedged = False
            if crypto_value > 0 and stable_value > 0:
                stable_ratio = stable_value / (crypto_value + stable_value)
                is_hedged = stable_ratio >= 0.2  # Consider hedged if at least 20% in stablecoins

            # Calculate risk level (1-5)
            risk_level = 3  # Default moderate risk
            if is_hedged:
                risk_level = 2  # Lower risk if hedged
            if market_volatility and market_volatility > 0.03:
                risk_level += 1  # Higher risk in volatile market
            if stable_ratio > 0.5:
                risk_level = 1  # Very low risk if majority in stablecoins

            # Create new summary
            db_obj = UserPortfolioSummary(
                user_id=user_id,
                timestamp=datetime.utcnow(),
                total_value=total_value,
                total_cost_basis=total_cost_basis,
                total_profit_loss=total_profit_loss,
                total_profit_loss_percentage=profit_loss_percentage,
                crypto_value=crypto_value,
                stable_value=stable_value,
                daily_change=daily_change,
                weekly_change=weekly_change,
                monthly_change=monthly_change,
                assets=assets,
                trades_today=trades_today,
                swaps_today=swaps_today,
                market_trend=market_trend,
                market_volatility=market_volatility,
                is_hedged=is_hedged,
                risk_level=risk_level
            )

            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            return db_obj

        except Exception as e:
            logger.error(f"Error creating portfolio summary: {str(e)}")
            raise

    async def get_latest_summary(
        self,
        db: AsyncSession,
        *,
        user_id: Optional[int] = None
    ) -> Optional[UserPortfolioSummary]:
        """
        Get the latest portfolio summary for a user
        """
        try:
            query = select(UserPortfolioSummary).order_by(desc(UserPortfolioSummary.timestamp))

            if user_id:
                query = query.filter(UserPortfolioSummary.user_id == user_id)

            result = await db.execute(query.limit(1))
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error getting latest portfolio summary: {str(e)}")
            raise

    async def get_historical_summaries(
        self,
        db: AsyncSession,
        *,
        user_id: Optional[int] = None,
        days: int = 7,
        interval: str = "daily"  # daily, hourly
    ) -> List[UserPortfolioSummary]:
        """
        Get historical portfolio summaries for charting/analysis
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            if interval == "hourly":
                # For hourly data, get all records within the time range
                query = select(UserPortfolioSummary)\
                    .filter(UserPortfolioSummary.timestamp >= start_date)\
                    .order_by(UserPortfolioSummary.timestamp)

                if user_id:
                    query = query.filter(UserPortfolioSummary.user_id == user_id)

                result = await db.execute(query)
                return result.scalars().all()
            else:
                # For daily data, get one record per day (closest to midnight)
                daily_summaries = []
                current_date = start_date

                while current_date < datetime.utcnow():
                    day_start = datetime(current_date.year, current_date.month, current_date.day)
                    day_end = day_start + timedelta(days=1)

                    query = select(UserPortfolioSummary)\
                        .filter(UserPortfolioSummary.timestamp >= day_start)\
                        .filter(UserPortfolioSummary.timestamp < day_end)

                    if user_id:
                        query = query.filter(UserPortfolioSummary.user_id == user_id)

                    query = query.order_by(desc(UserPortfolioSummary.timestamp)).limit(1)
                    result = await db.execute(query)
                    summary = result.scalars().first()

                    if summary:
                        daily_summaries.append(summary)

                    current_date += timedelta(days=1)

                return daily_summaries
        except Exception as e:
            logger.error(f"Error getting historical portfolio summaries: {str(e)}")
            raise


# Create instance
user_portfolio_summary_crud = CRUDUserPortfolioSummary(UserPortfolioSummary)
