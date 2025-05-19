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
        interval: str = "daily"  # daily, hourly, last_hour, minutes_15, minutes_5, minutes_1
    ) -> List[UserPortfolioSummary]:
        """
        Get historical portfolio summaries for charting/analysis

        Intervals:
        - daily: one record per day for the past 'days' days
        - hourly: all records for the past 'days' days
        - last_hour: all records from the last hour
        - minutes_15: all records from the last 15 minutes
        - minutes_5: all records from the last 5 minutes
        - minutes_1: all records from the last minute
        """
        try:
            # For predefined short intervals, override the days parameter
            if interval == "last_hour":
                start_date = datetime.utcnow() - timedelta(hours=1)
            elif interval == "minutes_15":
                start_date = datetime.utcnow() - timedelta(minutes=15)
            elif interval == "minutes_5":
                start_date = datetime.utcnow() - timedelta(minutes=5)
            elif interval == "minutes_1":
                start_date = datetime.utcnow() - timedelta(minutes=1)
            else:
                start_date = datetime.utcnow() - timedelta(days=days)

            # For all time-based intervals except daily, return all records in the time range
            if interval in ["hourly", "last_hour", "minutes_15", "minutes_5", "minutes_1"]:
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

    async def get_time_period_summary(
        self,
        db: AsyncSession,
        *,
        user_id: Optional[int] = None,
        time_period: str = "hour"  # hour, minutes_15, minutes_5, minutes_1
    ) -> Dict[str, Any]:
        """
        Get a summary of portfolio performance for a specific time period
        Returns start, end, and change metrics
        """
        try:
            # Determine time period
            now = datetime.utcnow()
            if time_period == "hour":
                start_time = now - timedelta(hours=1)
            elif time_period == "minutes_15":
                start_time = now - timedelta(minutes=15)
            elif time_period == "minutes_5":
                start_time = now - timedelta(minutes=5)
            elif time_period == "minutes_1":
                start_time = now - timedelta(minutes=1)
            else:
                start_time = now - timedelta(hours=1)  # Default to 1 hour

            # Get the earliest record in the time period
            earliest_query = select(UserPortfolioSummary)\
                .filter(UserPortfolioSummary.timestamp >= start_time)

            if user_id:
                earliest_query = earliest_query.filter(UserPortfolioSummary.user_id == user_id)

            earliest_query = earliest_query.order_by(UserPortfolioSummary.timestamp.asc()).limit(1)
            earliest_result = await db.execute(earliest_query)
            start_summary = earliest_result.scalars().first()

            # Get the latest record
            latest_query = select(UserPortfolioSummary)

            if user_id:
                latest_query = latest_query.filter(UserPortfolioSummary.user_id == user_id)

            latest_query = latest_query.order_by(desc(UserPortfolioSummary.timestamp)).limit(1)
            latest_result = await db.execute(latest_query)
            end_summary = latest_result.scalars().first()

            # If we didn't find records, return empty data
            if not start_summary or not end_summary:
                return {
                    "time_period": time_period,
                    "has_data": False,
                    "message": "No data available for the specified time period"
                }

            # Calculate changes
            value_change = end_summary.total_value - start_summary.total_value
            value_change_pct = (value_change / start_summary.total_value * 100) if start_summary.total_value > 0 else 0

            profit_change = end_summary.total_profit_loss - start_summary.total_profit_loss

            # Get all summaries in the time period for detailed analysis
            all_query = select(UserPortfolioSummary)\
                .filter(UserPortfolioSummary.timestamp >= start_time)

            if user_id:
                all_query = all_query.filter(UserPortfolioSummary.user_id == user_id)

            all_query = all_query.order_by(UserPortfolioSummary.timestamp.asc())
            all_result = await db.execute(all_query)
            all_summaries = all_result.scalars().all()

            # If we have enough data points, calculate volatility
            volatility = None
            if len(all_summaries) >= 3:
                values = [s.total_value for s in all_summaries]
                # Simple volatility calculation: standard deviation of returns
                try:
                    import numpy as np
                    if len(values) > 1:
                        returns = [(values[i] - values[i-1])/values[i-1] for i in range(1, len(values))]
                        volatility = float(np.std(returns) * 100) if returns else None
                except ImportError:
                    # Fall back to basic calculation if numpy is not available
                    if len(values) > 1:
                        returns = [(values[i] - values[i-1])/values[i-1] for i in range(1, len(values))]
                        if returns:
                            # Manual standard deviation calculation
                            mean = sum(returns) / len(returns)
                            variance = sum((r - mean) ** 2 for r in returns) / len(returns)
                            volatility = (variance ** 0.5) * 100

            return {
                "time_period": time_period,
                "has_data": True,
                "start_time": start_summary.timestamp.isoformat(),
                "end_time": end_summary.timestamp.isoformat(),
                "start_value": start_summary.total_value,
                "end_value": end_summary.total_value,
                "value_change": value_change,
                "value_change_percent": value_change_pct,
                "start_profit": start_summary.total_profit_loss,
                "end_profit": end_summary.total_profit_loss,
                "profit_change": profit_change,
                "data_points": len(all_summaries),
                "volatility": volatility,
                "start_market_trend": start_summary.market_trend,
                "end_market_trend": end_summary.market_trend
            }

        except Exception as e:
            logger.error(f"Error getting time period summary: {str(e)}")
            return {
                "time_period": time_period,
                "has_data": False,
                "error": str(e)
            }


# Create instance
user_portfolio_summary_crud = CRUDUserPortfolioSummary(UserPortfolioSummary)
