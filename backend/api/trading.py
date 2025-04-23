from fastapi import HTTPException
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from ..db.models import Trade, Config, TradeStatus, TradeType
from ..trader.strategy import StraddleStrategy
from ..services.telegram import TelegramService
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class TradingAPI:
    def __init__(self, db_session: Session, exchange_manager, telegram_service: TelegramService):
        self.db = db_session
        self.exchange = exchange_manager.get_exchange() if hasattr(exchange_manager, 'get_exchange') else exchange_manager
        self.telegram = telegram_service

    async def get_trades(
        self,
        status: Optional[TradeStatus] = None,
        coin: Optional[str] = None,
        limit: int = 100
    ) -> List[Trade]:
        """Get trades with optional filtering"""
        try:
            query = self.db.query(Trade)

            if status:
                query = query.filter(Trade.status == status)
            if coin:
                query = query.filter(Trade.coin == coin)

            return query.order_by(Trade.created_at.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"Error fetching trades: {str(e)}")
            raise HTTPException(status_code=500, detail="Error fetching trades")

    async def get_profit_summary(self, period: str = "daily") -> Dict:
        """Get profit/loss summary for trades"""
        try:
            # Calculate time range based on period
            now = datetime.now()
            if period == "daily":
                start_time = now - timedelta(days=1)
            elif period == "weekly":
                start_time = now - timedelta(weeks=1)
            elif period == "monthly":
                start_time = now - timedelta(days=30)
            else:
                raise HTTPException(status_code=400, detail="Invalid period")

            # Query trades within time range
            trades = self.db.query(Trade).filter(
                Trade.created_at >= start_time,
                Trade.status == TradeStatus.CLOSED
            ).all()

            # Calculate summary
            total_trades = len(trades)
            winning_trades = len([t for t in trades if t.profit_pct > 0])
            losing_trades = len([t for t in trades if t.profit_pct < 0])
            net_profit = sum(t.profit_pct for t in trades)
            best_trade = max(t.profit_pct for t in trades) if trades else 0
            worst_trade = min(t.profit_pct for t in trades) if trades else 0

            return {
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "net_profit": net_profit,
                "best_trade": best_trade,
                "worst_trade": worst_trade,
                "period": period
            }
        except Exception as e:
            logger.error(f"Error calculating profit summary: {str(e)}")
            raise HTTPException(status_code=500, detail="Error calculating profit summary")

    async def get_config(self, coin: Optional[str] = None) -> List[Config]:
        """Get trading configuration"""
        try:
            query = self.db.query(Config)
            if coin:
                query = query.filter(Config.coin == coin)
            return query.all()
        except Exception as e:
            logger.error(f"Error fetching config: {str(e)}")
            raise HTTPException(status_code=500, detail="Error fetching config")

    async def update_config(self, coin: str, config_data: Dict) -> Config:
        """Update trading configuration"""
        try:
            config = self.db.query(Config).filter(Config.coin == coin).first()
            if not config:
                config = Config(coin=coin)
                self.db.add(config)

            # Update config fields
            for key, value in config_data.items():
                if hasattr(config, key):
                    setattr(config, key, value)

            self.db.commit()
            return config
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating config: {str(e)}")
            raise HTTPException(status_code=500, detail="Error updating config")

    async def manual_trade(self, trade_data: Dict) -> Trade:
        """Execute a manual trade"""
        try:
            # Validate required fields
            required_fields = ["symbol", "quantity", "breakout_pct", "tp_pct", "sl_pct"]
            for field in required_fields:
                if field not in trade_data:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Missing required field: {field}"
                    )

            # Create strategy instance with the actual exchange
            strategy = StraddleStrategy(
                self.exchange,
                {
                    "breakout_pct": trade_data["breakout_pct"],
                    "tp_pct": trade_data["tp_pct"],
                    "sl_pct": trade_data["sl_pct"],
                    "quantity": trade_data["quantity"],
                    "paper_trading": True  # Always use paper trading for manual trades
                }
            )

            # Execute strategy
            trade = await strategy.execute_strategy(trade_data["symbol"])

            # Save trade to database
            self.db.add(trade)
            self.db.commit()

            # Send notification
            await self.telegram.send_trade_notification(
                "MANUAL",
                trade_data["symbol"],
                trade.entry_price,
                trade.quantity
            )

            return trade
        except HTTPException as he:
            self.db.rollback()
            raise he
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error executing manual trade: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
