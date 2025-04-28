from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from ..models.portfolio import Portfolio, Transaction
from .base import CRUDBase

class CRUDPortfolio(CRUDBase[Portfolio, Dict, Dict]):
    def get_by_user_and_symbol(
        self,
        db: Session,
        user_id: int,
        symbol: str
    ) -> Optional[Portfolio]:
        """Get portfolio entry by user_id and symbol"""
        return db.query(Portfolio).filter(
            Portfolio.user_id == user_id,
            Portfolio.symbol == symbol
        ).first()

    def get_user_portfolio(
        self,
        db: Session,
        user_id: int,
        active_only: bool = True
    ) -> List[Portfolio]:
        """Get all portfolio entries for a user"""
        query = db.query(Portfolio).filter(Portfolio.user_id == user_id)
        if active_only:
            query = query.filter(Portfolio.quantity > 0)
        return query.all()

    def update_portfolio(
        self,
        db: Session,
        portfolio: Portfolio,
        type: str,
        quantity: float,
        price: float
    ) -> Portfolio:
        """Update portfolio with new transaction"""
        if type.upper() == 'BUY':
            total_value = (portfolio.quantity * portfolio.avg_buy_price) + (quantity * price)
            new_quantity = portfolio.quantity + quantity
            portfolio.avg_buy_price = total_value / new_quantity if new_quantity > 0 else price
            portfolio.quantity = new_quantity
        else:  # SELL
            portfolio.quantity -= quantity

        portfolio.last_updated = datetime.utcnow()
        db.commit()
        db.refresh(portfolio)
        return portfolio

class CRUDTransaction(CRUDBase[Transaction, Dict, Dict]):
    def create_transaction(
        self,
        db: Session,
        user_id: int,
        portfolio_id: int,
        symbol: str,
        type: str,
        quantity: float,
        price: float
    ) -> Transaction:
        """Create a new transaction"""
        transaction = Transaction(
            user_id=user_id,
            portfolio_id=portfolio_id,
            symbol=symbol,
            type=type.upper(),
            quantity=quantity,
            price=price,
            total=quantity * price
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        return transaction

    def get_user_transactions(
        self,
        db: Session,
        user_id: int,
        symbol: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Transaction]:
        """Get user's transaction history with optional filters"""
        query = db.query(Transaction).filter(Transaction.user_id == user_id)

        if symbol:
            query = query.filter(Transaction.symbol == symbol)
        if start_date:
            query = query.filter(Transaction.timestamp >= start_date)
        if end_date:
            query = query.filter(Transaction.timestamp <= end_date)

        return query.order_by(Transaction.timestamp.desc()).limit(limit).all()

    def get_profit_summary(
        self,
        db: Session,
        user_id: int,
        timeframe: str = 'all'
    ) -> Dict:
        """Get profit summary for specified timeframe"""
        query = db.query(
            func.sum(Transaction.total).label('total_invested'),
            func.count().label('total_trades')
        ).filter(Transaction.user_id == user_id)

        if timeframe != 'all':
            now = datetime.utcnow()
            if timeframe == 'daily':
                start_date = now - timedelta(days=1)
            elif timeframe == 'weekly':
                start_date = now - timedelta(days=7)
            elif timeframe == 'monthly':
                start_date = now - timedelta(days=30)
            query = query.filter(Transaction.timestamp >= start_date)

        result = query.first()
        return {
            'total_invested': result.total_invested or 0,
            'total_trades': result.total_trades or 0
        }

    def get_straddle_transactions(
        self,
        db: Session,
        user_id: int,
        symbol: Optional[str] = None
    ) -> List[Transaction]:
        """Get straddle transactions for a user"""
        query = db.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.type.in_(['BUY', 'SELL'])
        )

        if symbol:
            query = query.filter(Transaction.symbol == symbol)

        return query.order_by(Transaction.timestamp.desc()).all()

# Create instances
portfolio = CRUDPortfolio(Portfolio)
transaction = CRUDTransaction(Transaction)
