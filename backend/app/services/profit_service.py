from typing import List, Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logger import logger
from app.services.helper.profit_calculator import profit_calculator
from app.crud.crud_trade import trade as trade_crud
from app.crud.crud_swap_transaction import swap_transaction_crud
from app.crud.curd_position import position_crud

class ProfitService:
    def __init__(self, db: AsyncSession = None):
        self.db = db

    async def get_position_profit(
        self,
        position_id: int,
        include_swaps: bool = True
    ) -> Dict:
        """
        Calculate profit for a specific position

        Args:
            position_id: Position ID to calculate profit for
            include_swaps: Whether to include swap transactions in the calculation

        Returns:
            Dictionary with profit calculation results
        """
        try:
            # Get position details
            position = await position_crud.get(self.db, id=position_id)
            if not position:
                logger.warning(f"Position {position_id} not found")
                return {"error": "Position not found", "position_id": position_id}

            # Get all trades for this position
            trades = await trade_crud.get_multi_by_position(self.db, position_id=position_id)

            # Format trades for profit calculator
            formatted_trades = []
            for trade in trades:
                # Skip trades with no timestamp data
                if (trade.side == "BUY" and trade.entered_at is None) or (trade.side == "SELL" and trade.closed_at is None and trade.entered_at is None):
                    continue

                formatted_trades.append({
                    "id": trade.id,
                    "symbol": trade.symbol,
                    "side": trade.side,
                    "quantity": trade.quantity,
                    "price": trade.entry_price if trade.side == "BUY" else trade.exit_price or trade.entry_price,
                    "fee": 0,  # Add fee if available
                    "timestamp": trade.entered_at if trade.side == "BUY" else trade.closed_at or trade.entered_at,
                    "position_id": trade.position_id
                })

            # Calculate trade profits
            trade_profits = profit_calculator.calculate_position_profit(formatted_trades)

            # Include swap transactions if requested
            swap_profits = {}
            if include_swaps:
                # Get all swaps for this position
                swaps = await swap_transaction_crud.get_by_position(self.db, position_id=position_id)

                # Format swaps for profit calculator
                formatted_swaps = []
                for swap in swaps:
                    # Skip swaps with no timestamp data
                    if swap.timestamp is None:
                        continue

                    formatted_swaps.append({
                        "id": swap.id,
                        "from_symbol": swap.from_symbol,
                        "to_symbol": swap.to_symbol,
                        "from_amount": swap.from_amount,
                        "to_amount": swap.to_amount,
                        "rate": swap.rate,
                        "fee": swap.fee_amount,
                        "timestamp": swap.timestamp,
                        "position_id": swap.position_id
                    })

                # Calculate swap profits
                swap_profits = profit_calculator.calculate_swap_profits(formatted_swaps)

            # Combine results
            combined_results = {
                "position_id": position_id,
                "symbol": position.symbol,
                "position_status": position.status,
                # "position_created_at": position.created_at,
                # "position_closed_at": position.closed_at,
                "strategy": position.strategy,
                "total_quantity": position.total_quantity,
                "average_entry_price": position.average_entry_price,
                "trade_results": trade_profits,
                "swap_results": swap_profits if include_swaps else None,
                "combined_profit": trade_profits["total_profit"] + (swap_profits.get("total_profit", 0) if include_swaps else 0),
                "combined_fee": trade_profits["total_fee"] + (swap_profits.get("total_fee", 0) if include_swaps else 0),
            }

            return combined_results

        except Exception as e:
            logger.error(f"Error calculating position profit: {str(e)}")
            return {"error": f"Failed to calculate profit: {str(e)}", "position_id": position_id}

    async def get_profit_by_date_range(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        symbol: Optional[str] = None
    ) -> Dict:
        """
        Calculate profit for a specific date range

        Args:
            start_date: Start date for the calculation
            end_date: End date for the calculation (defaults to now)
            symbol: Optional symbol to filter by

        Returns:
            Dictionary with profit calculation results
        """
        try:
            # Default end date to now if not provided
            if end_date is None:
                end_date = datetime.now()

            # Get all trades in the date range
            trades = await trade_crud.get_trades_by_date_range(
                self.db,
                start_date=start_date,
                end_date=end_date,
                symbol=symbol
            )

            # Format trades for profit calculator
            formatted_trades = []
            for trade in trades:
                # Skip trades with no timestamp data
                if (trade.side == "BUY" and trade.entered_at is None) or (trade.side == "SELL" and trade.closed_at is None and trade.entered_at is None):
                    continue

                formatted_trades.append({
                    "id": trade.id,
                    "symbol": trade.symbol,
                    "side": trade.side,
                    "quantity": trade.quantity,
                    "price": trade.entry_price if trade.side == "BUY" else trade.exit_price or trade.entry_price,
                    "fee": 0,  # Add fee if available
                    "timestamp": trade.entered_at if trade.side == "BUY" else trade.closed_at or trade.entered_at,
                    "position_id": trade.position_id
                })

            # Calculate trade profits
            trade_profits = profit_calculator.calculate_position_profit(
                formatted_trades,
                start_time=start_date,
                end_time=end_date
            )

            # Get all swaps in the date range
            swaps = await swap_transaction_crud.get_by_date_range(
                self.db,
                start_date=start_date,
                end_date=end_date,
                symbol=symbol
            )

            # Format swaps for profit calculator
            formatted_swaps = []
            for swap in swaps:
                # Skip swaps with no timestamp data
                if swap.created_at is None:
                    continue

                formatted_swaps.append({
                    "id": swap.id,
                    "from_symbol": swap.from_symbol,
                    "to_symbol": swap.to_symbol,
                    "from_amount": swap.from_amount,
                    "to_amount": swap.to_amount,
                    "rate": swap.rate,
                    "fee": swap.fee_amount,
                    "timestamp": swap.created_at,
                    "position_id": swap.position_id
                })

            # Calculate swap profits
            swap_profits = profit_calculator.calculate_swap_profits(
                formatted_swaps,
                start_time=start_date,
                end_time=end_date
            )

            # Combine results
            combined_results = {
                "start_date": start_date,
                "end_date": end_date,
                "symbol": symbol,
                "trade_results": trade_profits,
                "swap_results": swap_profits,
                "combined_profit": trade_profits["total_profit"] + swap_profits["total_profit"],
                "combined_fee": trade_profits["total_fee"] + swap_profits["total_fee"],
                "total_trades": len(formatted_trades),
                "total_swaps": len(formatted_swaps),
                "positions": list(set(t.get("position_id") for t in formatted_trades if t.get("position_id"))),
                "symbols_traded": list(set(t.get("symbol") for t in formatted_trades)),
                "symbols_swapped": list(set([s.get("from_symbol") for s in formatted_swaps] + [s.get("to_symbol") for s in formatted_swaps])),
            }

            return combined_results

        except Exception as e:
            logger.error(f"Error calculating profit by date range: {str(e)}")
            return {"error": f"Failed to calculate profit: {str(e)}", "start_date": start_date, "end_date": end_date}

    async def get_profit_summary(self) -> Dict:
        """
        Get an overall profit summary

        Returns:
            Dictionary with profit summary data
        """
        try:
            # Get summary data for different time periods
            day_ago = datetime.now() - timedelta(days=1)
            week_ago = datetime.now() - timedelta(days=7)
            month_ago = datetime.now() - timedelta(days=30)

            # Calculate profits for each period
            daily_profits = await self.get_profit_by_date_range(day_ago)
            weekly_profits = await self.get_profit_by_date_range(week_ago)
            monthly_profits = await self.get_profit_by_date_range(month_ago)

            # Get all active positions
            active_positions = await position_crud.get_active_positions(self.db)

            # Format response
            summary = {
                "daily_profit": daily_profits.get("combined_profit", 0),
                "weekly_profit": weekly_profits.get("combined_profit", 0),
                "monthly_profit": monthly_profits.get("combined_profit", 0),
                "daily_trades": daily_profits.get("total_trades", 0),
                "weekly_trades": weekly_profits.get("total_trades", 0),
                "monthly_trades": monthly_profits.get("total_trades", 0),
                "daily_swaps": daily_profits.get("total_swaps", 0),
                "weekly_swaps": weekly_profits.get("total_swaps", 0),
                "monthly_swaps": monthly_profits.get("total_swaps", 0),
                "active_positions_count": len(active_positions),
                "active_positions": [
                    {
                        "id": pos.id,
                        "symbol": pos.symbol,
                        "strategy": pos.strategy,
                        "total_quantity": pos.total_quantity,
                        "average_entry_price": pos.average_entry_price,
                        "created_at": pos.created_at,
                    }
                    for pos in active_positions
                ],
                "timestamp": datetime.now()
            }

            return summary

        except Exception as e:
            logger.error(f"Error calculating profit summary: {str(e)}")
            return {"error": f"Failed to calculate profit summary: {str(e)}"}

# Create singleton instance
profit_service = ProfitService()
