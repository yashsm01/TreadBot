from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.crud.crud_position import position as position_crud
from app.crud.crud_trade import trade as trade_crud
from app.core.logger import logger
from app.services.market_analyzer import market_analyzer

class PortfolioService:
    @staticmethod
    async def get_portfolio_summary(db: Session) -> Dict:
        """Get overall portfolio summary"""
        try:
            # Get all positions
            positions = position_crud.get_multi(db)

            # Calculate portfolio metrics
            total_realized_pnl = sum(pos.realized_pnl for pos in positions)
            total_unrealized_pnl = sum(pos.unrealized_pnl for pos in positions)
            total_pnl = total_realized_pnl + total_unrealized_pnl

            # Count positions by status
            active_positions = len([p for p in positions if p.status == "ACTIVE"])
            closed_positions = len([p for p in positions if p.status == "CLOSED"])

            return {
                "total_realized_pnl": total_realized_pnl,
                "total_unrealized_pnl": total_unrealized_pnl,
                "total_pnl": total_pnl,
                "active_positions": active_positions,
                "closed_positions": closed_positions,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting portfolio summary: {str(e)}")
            raise

    @staticmethod
    async def get_position_metrics(
        db: Session,
        symbol: Optional[str] = None
    ) -> List[Dict]:
        """Get detailed metrics for positions"""
        try:
            if symbol:
                positions = position_crud.get_by_symbol(db, symbol=symbol)
            else:
                positions = position_crud.get_multi(db)

            metrics = []
            for pos in positions:
                # Get market conditions
                market_data = await market_analyzer.check_market_conditions(pos.symbol)

                metrics.append({
                    "position_id": pos.id,
                    "symbol": pos.symbol,
                    "strategy": pos.strategy,
                    "total_quantity": pos.total_quantity,
                    "average_entry": pos.average_entry_price,
                    "realized_pnl": pos.realized_pnl,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "status": pos.status,
                    "market_conditions": market_data,
                    "open_time": pos.open_time.isoformat(),
                    "close_time": pos.close_time.isoformat() if pos.close_time else None
                })

            return metrics
        except Exception as e:
            logger.error(f"Error getting position metrics: {str(e)}")
            raise

    @staticmethod
    async def get_trading_performance(
        db: Session,
        days: int = 30
    ) -> Dict:
        """Get trading performance statistics"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            # Get trades within date range
            trades = trade_crud.get_multi(db)
            recent_trades = [
                t for t in trades
                if t.entry_time >= start_date
            ]

            # Calculate performance metrics
            total_trades = len(recent_trades)
            winning_trades = len([t for t in recent_trades if t.pnl and t.pnl > 0])
            losing_trades = len([t for t in recent_trades if t.pnl and t.pnl < 0])

            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

            # Calculate profit metrics
            total_profit = sum(t.pnl for t in recent_trades if t.pnl and t.pnl > 0)
            total_loss = sum(t.pnl for t in recent_trades if t.pnl and t.pnl < 0)

            profit_factor = abs(total_profit / total_loss) if total_loss != 0 else float('inf')

            return {
                "period_days": days,
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "win_rate": win_rate,
                "total_profit": total_profit,
                "total_loss": total_loss,
                "profit_factor": profit_factor,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting trading performance: {str(e)}")
            raise

    @staticmethod
    async def check_risk_limits(
        db: Session,
        symbol: str,
        quantity: float,
        price: float
    ) -> Dict:
        """Check if trade meets risk management criteria"""
        try:
            # Get portfolio summary
            portfolio = await PortfolioService.get_portfolio_summary(db)

            # Calculate position size
            position_value = quantity * price

            # Get market volatility
            volatility = await market_analyzer.calculate_volatility(symbol)

            # Define risk limits
            MAX_POSITION_SIZE = 0.2  # 20% of portfolio
            MAX_DAILY_LOSS = 0.02    # 2% max daily loss
            MAX_VOLATILITY = 0.5     # 50% annualized volatility

            # Check limits
            position_size_ok = position_value <= (portfolio['total_pnl'] * MAX_POSITION_SIZE)
            volatility_ok = volatility <= MAX_VOLATILITY

            return {
                "position_size_ok": position_size_ok,
                "volatility_ok": volatility_ok,
                "max_position_size": portfolio['total_pnl'] * MAX_POSITION_SIZE,
                "current_position_size": position_value,
                "current_volatility": volatility,
                "max_volatility": MAX_VOLATILITY,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error checking risk limits: {str(e)}")
            raise

portfolio_service = PortfolioService()
