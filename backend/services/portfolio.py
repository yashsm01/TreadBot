import logging
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from ..models.portfolio import Portfolio, Transaction
from ..trader.exchange_manager import ExchangeManager

logger = logging.getLogger(__name__)

class PortfolioService:
    def __init__(self, db: Session, exchange_manager: ExchangeManager):
        self.db = db
        self.exchange_manager = exchange_manager

    async def add_transaction(self, user_id: int, symbol: str, type: str, quantity: float, price: float) -> Dict:
        """Add a new transaction and update portfolio"""
        try:
            # Create transaction record
            total = quantity * price
            transaction = Transaction(
                user_id=user_id,
                symbol=symbol,
                type=type.upper(),
                quantity=quantity,
                price=price,
                total=total
            )
            self.db.add(transaction)

            # Update portfolio
            portfolio = self.db.query(Portfolio).filter(
                Portfolio.user_id == user_id,
                Portfolio.symbol == symbol
            ).first()

            if not portfolio:
                if type.upper() == 'SELL':
                    raise ValueError("Cannot sell without existing position")
                portfolio = Portfolio(
                    user_id=user_id,
                    symbol=symbol,
                    quantity=quantity,
                    avg_buy_price=price
                )
                self.db.add(portfolio)
            else:
                if type.upper() == 'BUY':
                    # Update average buy price
                    total_value = (portfolio.quantity * portfolio.avg_buy_price) + (quantity * price)
                    new_quantity = portfolio.quantity + quantity
                    portfolio.avg_buy_price = total_value / new_quantity
                    portfolio.quantity = new_quantity
                else:  # SELL
                    if quantity > portfolio.quantity:
                        raise ValueError(f"Insufficient quantity. Available: {portfolio.quantity}")
                    portfolio.quantity -= quantity

            self.db.commit()
            return {
                "status": "success",
                "transaction_id": transaction.id,
                "type": type,
                "symbol": symbol,
                "quantity": quantity,
                "price": price,
                "total": total
            }
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error adding transaction: {str(e)}")
            raise

    async def get_portfolio(self, user_id: int) -> List[Dict]:
        """Get user's current portfolio with live prices"""
        try:
            portfolio_items = self.db.query(Portfolio).filter(
                Portfolio.user_id == user_id,
                Portfolio.quantity > 0
            ).all()

            result = []
            total_invested = 0
            total_current_value = 0

            for item in portfolio_items:
                # Get current price
                ticker = await self.exchange_manager.get_ticker(item.symbol)
                if ticker is None:
                    logger.error(f"Could not get ticker for {item.symbol}")
                    continue
                current_price = ticker['last']

                current_value = item.quantity * current_price
                invested_value = item.quantity * item.avg_buy_price
                profit_loss = current_value - invested_value
                profit_loss_pct = (profit_loss / invested_value) * 100 if invested_value > 0 else 0

                total_invested += invested_value
                total_current_value += current_value

                result.append({
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

            return {
                "portfolio": result,
                "summary": {
                    "total_invested": total_invested,
                    "total_current_value": total_current_value,
                    "total_profit_loss": total_current_value - total_invested,
                    "total_profit_loss_pct": ((total_current_value - total_invested) / total_invested * 100) if total_invested > 0 else 0
                }
            }
        except Exception as e:
            logger.error(f"Error getting portfolio: {str(e)}")
            raise

    async def get_transaction_history(self, user_id: int, symbol: Optional[str] = None) -> List[Dict]:
        """Get user's transaction history"""
        try:
            query = self.db.query(Transaction).filter(Transaction.user_id == user_id)
            if symbol:
                query = query.filter(Transaction.symbol == symbol)

            transactions = query.order_by(Transaction.timestamp.desc()).all()

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
            query = self.db.query(
                func.sum(Transaction.total).label('total_invested'),
                func.count().label('total_trades')
            ).filter(Transaction.user_id == user_id)

            if timeframe != 'all':
                if timeframe == 'daily':
                    date_filter = func.date(Transaction.timestamp) == func.current_date()
                elif timeframe == 'weekly':
                    date_filter = func.date(Transaction.timestamp) >= func.date_sub(func.current_date(), 7)
                elif timeframe == 'monthly':
                    date_filter = func.date(Transaction.timestamp) >= func.date_sub(func.current_date(), 30)
                query = query.filter(date_filter)

            result = query.first()

            portfolio = await self.get_portfolio(user_id)

            return {
                "timeframe": timeframe,
                "total_invested": result.total_invested or 0,
                "total_current_value": portfolio['summary']['total_current_value'],
                "total_profit_loss": portfolio['summary']['total_profit_loss'],
                "total_profit_loss_pct": portfolio['summary']['total_profit_loss_pct'],
                "total_trades": result.total_trades,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting profit summary: {str(e)}")
            raise
