import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.crud.crud_portfolio import portfolio_crud as portfolio_crud
from app.crud.crud_portfolio import transaction_crud as transaction_crud
from app.core.exchange.exchange_manager import exchange_manager
from app.core.logger import logger
from app.services.market_analyzer import market_analyzer as market_analyzer
from app.crud.curd_position import position_crud as position_crud
from app.core.config import settings
from app.models.trade import Trade
from app.crud.crud_trade import trade as trade_crud
from app.services.notifications import notification_service

class PortfolioService:
    def __init__(self, db: Session):
        self.db = db
        self.exchange_manager = exchange_manager

    async def get_portfolio_summary(self, user_id: int) -> Dict:
        """Get overall portfolio summary"""
        try:
            # Get user's portfolio
            portfolio = await self.get_portfolio(user_id)

            # Calculate metrics
            total_realized_pnl = 0
            total_unrealized_pnl = 0
            active_positions = 0

            for position in portfolio['portfolio']:
                if position['quantity'] > 0:
                    active_positions += 1
                    total_unrealized_pnl += position['profit_loss']

            # Get historical transactions for realized PnL
            transactions = await self.get_transaction_history(user_id)
            for tx in transactions:
                if tx['type'] == 'SELL':
                    total_realized_pnl += tx['total'] - (tx['quantity'] * tx['price'])

            return {
                "total_realized_pnl": total_realized_pnl,
                "total_unrealized_pnl": total_unrealized_pnl,
                "total_pnl": total_realized_pnl + total_unrealized_pnl,
                "active_positions": active_positions,
                "total_positions": len(portfolio['portfolio']),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting portfolio summary: {str(e)}")
            if hasattr(self.db, 'rollback'):
                self.db.rollback()
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

    async def add_transaction(
        self,
        user_id: int,
        symbol: str,
        type: str,
        quantity: float,
        price: float
    ) -> Dict:
        """Add a new transaction and update portfolio"""
        try:
            # Start a new transaction
            if hasattr(self.db, 'begin_nested'):
                savepoint = self.db.begin_nested()

            try:
                # Check risk limits
                # risk_check = await self.check_risk_limits(user_id, symbol, quantity, price)
                # if not risk_check['position_size_ok'] or not risk_check['volatility_ok']:
                #     raise ValueError("Trade exceeds risk limits")

                # Get or create portfolio
                portfolio = portfolio_crud.get_by_user_and_symbol(self.db, user_id, symbol)

                if not portfolio:
                    if type.upper() == 'SELL':
                        raise ValueError("Cannot sell without existing position")
                    portfolio = portfolio_crud.create(
                        self.db,
                        obj_in={
                            "user_id": user_id,
                            "symbol": symbol,
                            "quantity": 0,
                            "avg_buy_price": price
                        }
                    )

                # Validate sell transaction
                if type.upper() == 'SELL' and quantity > portfolio.quantity:
                    raise ValueError(f"Insufficient quantity. Available: {portfolio.quantity}")

                # Create transaction
                transaction = transaction_crud.create_transaction(
                    self.db,
                    user_id=user_id,
                    portfolio_id=portfolio.id,
                    symbol=symbol,
                    type=type,
                    quantity=quantity,
                    price=price
                )

                # Update portfolio
                portfolio = portfolio_crud.update_portfolio(
                    self.db,
                    portfolio=portfolio,
                    type=type,
                    quantity=quantity,
                    price=price
                )

                # Commit the transaction
                if hasattr(self.db, 'commit'):
                    self.db.commit()

                return {
                    "status": "success",
                    "transaction_id": transaction.id,
                    "type": type,
                    "symbol": symbol,
                    "quantity": quantity,
                    "price": price,
                    "total": transaction.total
                }

            except Exception as e:
                if hasattr(self.db, 'rollback'):
                    self.db.rollback()
                raise e
            finally:
                if hasattr(self.db, 'close'):
                    self.db.close()

        except Exception as e:
            logger.error(f"Error adding transaction: {str(e)}")
            if hasattr(self.db, 'rollback'):
                self.db.rollback()
            raise

    async def get_portfolio(self, user_id: int) -> Dict:
        """Get user's current portfolio with live prices"""
        try:
            portfolio_items = []
            total_invested = 0
            total_current_value = 0

            # Start a new transaction
            if hasattr(self.db, 'begin_nested'):
                savepoint = self.db.begin_nested()

            try:
                # Get portfolio items with quantity > 0
                portfolio_items_db = portfolio_crud.get_user_portfolio(self.db, user_id)

                # Initialize exchange manager if needed
                if not self.exchange_manager._initialized:
                    await self.exchange_manager.initialize()

                for item in portfolio_items_db:
                    # Get current price
                    ticker = await self.exchange_manager.get_ticker(item.symbol)
                    if not ticker:
                        logger.error(f"Could not get ticker for {item.symbol}")
                        continue

                    current_price = ticker['last']
                    current_value = item.quantity * current_price
                    invested_value = item.quantity * item.avg_buy_price
                    profit_loss = current_value - invested_value
                    profit_loss_pct = (profit_loss / invested_value) * 100 if invested_value > 0 else 0

                    total_invested += invested_value
                    total_current_value += current_value

                    portfolio_items.append({
                        "symbol": item.symbol,
                        "quantity": item.quantity,
                        "avg_buy_price": item.avg_buy_price,
                        "current_price": current_price,
                        "current_value": current_value,
                        "invested_value": invested_value,
                        "profit_loss": profit_loss,
                        "profit_loss_pct": profit_loss_pct,
                        "last_updated": item.last_updated.isoformat()
                    })

                if hasattr(self.db, 'commit'):
                    self.db.commit()

                return {
                    "portfolio": portfolio_items,
                    "summary": {
                        "total_invested": total_invested,
                        "total_current_value": total_current_value,
                        "total_profit_loss": total_current_value - total_invested,
                        "total_profit_loss_pct": ((total_current_value - total_invested) / total_invested * 100) if total_invested > 0 else 0
                    }
                }
            except Exception as e:
                if hasattr(self.db, 'rollback'):
                    self.db.rollback()
                raise e
            finally:
                if hasattr(self.db, 'close'):
                    self.db.close()

        except Exception as e:
            logger.error(f"Error getting portfolio: {str(e)}")
            if hasattr(self.db, 'rollback'):
                self.db.rollback()
            raise

    async def get_transaction_history(
        self,
        user_id: int,
        symbol: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """Get user's transaction history"""
        try:
            transactions = transaction_crud.get_user_transactions(
                self.db,
                user_id=user_id,
                symbol=symbol,
                start_date=start_date,
                end_date=end_date
            )

            return [{
                "id": tx.id,
                "symbol": tx.symbol,
                "type": tx.type,
                "quantity": tx.quantity,
                "price": tx.price,
                "total": tx.total,
                "timestamp": tx.timestamp.isoformat()
            } for tx in transactions]
        except Exception as e:
            logger.error(f"Error getting transaction history: {str(e)}")
            raise

    async def get_profit_summary(self, user_id: int, timeframe: str = 'all') -> Dict:
        """Get profit/loss summary for specified timeframe"""
        try:
            # Get transaction summary
            summary = transaction_crud.get_profit_summary(self.db, user_id, timeframe)

            # Get current portfolio value
            portfolio = await self.get_portfolio(user_id)

            return {
                "timeframe": timeframe,
                "total_invested": summary['total_invested'],
                "total_current_value": portfolio['summary']['total_current_value'],
                "total_profit_loss": portfolio['summary']['total_profit_loss'],
                "total_profit_loss_pct": portfolio['summary']['total_profit_loss_pct'],
                "total_trades": summary['total_trades'],
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting profit summary: {str(e)}")
            raise

    async def check_risk_limits(
        self,
        user_id: int,
        symbol: str,
        quantity: float,
        price: float
    ) -> Dict:
        """Check if trade meets risk management criteria"""
        try:
            # Get portfolio summary
            portfolio = await self.get_portfolio_summary(user_id)

            # Calculate position size
            position_value = quantity * price
            portfolio_value = portfolio['total_pnl']

            # Get market volatility
            volatility = await market_analyzer.calculate_volatility(symbol)

            # Define risk limits
            MAX_POSITION_SIZE = 0.2  # 20% of portfolio
            MAX_VOLATILITY = 0.5     # 50% annualized volatility

            # Check limits
            position_size_ok = position_value <= (portfolio_value * MAX_POSITION_SIZE) if portfolio_value > 0 else True
            volatility_ok = volatility <= MAX_VOLATILITY

            return {
                "position_size_ok": position_size_ok,
                "volatility_ok": volatility_ok,
                "max_position_size": portfolio_value * MAX_POSITION_SIZE if portfolio_value > 0 else float('inf'),
                "current_position_size": position_value,
                "current_volatility": volatility,
                "max_volatility": MAX_VOLATILITY,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error checking risk limits: {str(e)}")
            raise

    async def get_straddle_positions(self, user_id: int, symbol: Optional[str] = None) -> List[Dict]:
        """Get all active straddle positions for a user"""
        try:
            transactions = transaction_crud.get_straddle_transactions(self.db, user_id, symbol)

            positions = []
            straddle_pairs = {}

            # Initialize exchange manager if needed
            if not self.exchange_manager._initialized:
                await self.exchange_manager.initialize()

            # Group transactions by symbol and timestamp
            for tx in transactions:
                key = f"{tx.symbol}_{tx.timestamp.strftime('%Y%m%d%H%M%S')}"
                if key not in straddle_pairs:
                    straddle_pairs[key] = []
                straddle_pairs[key].append(tx)

            # Process valid straddle pairs
            for key, pair in straddle_pairs.items():
                if len(pair) == 2 and pair[0].type != pair[1].type:
                    # Get current market price
                    ticker = await self.exchange_manager.get_ticker(pair[0].symbol)
                    if not ticker:
                        continue

                    current_price = ticker['last']
                    buy_tx = next(tx for tx in pair if tx.type == 'BUY')

                    positions.append({
                        "position_id": buy_tx.id,
                        "symbol": buy_tx.symbol,
                        "quantity": buy_tx.quantity,
                        "strike_price": buy_tx.price,
                        "current_price": current_price,
                        "open_time": buy_tx.timestamp.isoformat()
                    })

            return positions
        except Exception as e:
            logger.error(f"Error getting straddle positions: {str(e)}")
            return []

    async def execute_trade(
        self,
        db: Session,
        symbol: str,
        quantity: float,
        side: str,
        price: float,
        user_id: int
    ) -> Dict:
        """Execute a trade and update portfolio"""
        try:
            # Validate side
            if side.upper() not in ["BUY", "SELL"]:
                raise ValueError("Invalid trade side. Must be 'BUY' or 'SELL'")

            # Add transaction
            transaction = await self.add_transaction(
                user_id=user_id,
                symbol=symbol,
                type=side.upper(),
                quantity=quantity,
                price=price
            )

            return {
                "status": "success",
                "symbol": symbol,
                "side": side.upper(),
                "quantity": quantity,
                "price": price,
                "total": transaction["total"],
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error executing trade: {str(e)}")
            raise

# Create singleton instance
portfolio_service = PortfolioService(None)  # DB session will be injected later
