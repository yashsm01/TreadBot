from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import pandas as pd
from app.core.logger import logger
from app.core.config import settings
from app.models.trade import Trade
from app.schemas.trade import TradeCreate
from app.crud.crud_trade import trade as trade_crud
from app.services.helper.market_analyzer import MarketAnalyzer, BreakoutSignal
from app.services.notifications import notification_service
from sqlalchemy import select

class StraddleStrategy:
    def __init__(self):
        self.breakout_threshold = 0.01  # 1% breakout threshold
        self.min_confidence = 0.7  # Minimum confidence for breakout signals
        self.position_size = 1.0  # Default position size in base currency

    def calculate_entry_levels(self, current_price: float) -> Tuple[float, float]:
        """Calculate entry levels for straddle"""
        buy_entry = current_price * (1 + self.breakout_threshold)
        sell_entry = current_price * (1 - self.breakout_threshold)
        return buy_entry, sell_entry

    def calculate_position_params(self, entry_price: float, direction: str) -> Tuple[float, float]:
        """Calculate TP and SL as percentage-based price deltas."""

        if entry_price <= 0:
            raise ValueError("Entry price must be greater than 0.")

        direction = direction.upper()
        if direction not in ("UP", "DOWN"):
            raise ValueError("Direction must be 'UP' or 'DOWN'.")

        tp_pct = settings.DEFAULT_TP_PCT  # Example: 0.01 for 1%
        sl_pct = settings.DEFAULT_SL_PCT  # Example: 0.01 for 1%

        tp_amount = (entry_price * tp_pct)/ 100
        sl_amount = (entry_price * sl_pct)/ 100

        if direction == "UP":
            take_profit = entry_price + tp_amount
            stop_loss = entry_price - sl_amount
        else:  # DOWN (short)
            take_profit = entry_price - tp_amount
            stop_loss = entry_price + sl_amount

        return round(take_profit, 2), round(stop_loss, 2)
class StraddleService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.strategy = StraddleStrategy()

    async def analyze_market_conditions(self,
                                      symbol: str,
                                      prices: pd.Series,
                                      volume: pd.Series) -> Dict:
        """
        Analyze market conditions for potential straddle setup
        Returns detailed analysis including market conditions and any breakout signals
        """
        analysis = await MarketAnalyzer.analyze_breakout(symbol, prices, volume)

        if analysis.get("validation_error"):
            logger.warning(f"Validation error in market analysis: {analysis['message']}")
            return {
                "success": False,
                "message": analysis["message"],
                "validation_error": True
            }

        if analysis.get("error"):
            logger.error(f"Error in market analysis: {analysis['message']}")
            return {
                "success": False,
                "message": analysis["message"],
                "error": True
            }

        response = {
            "success": True,
            "has_signal": analysis["has_signal"],
            "message": analysis["message"],
            "market_conditions": analysis["market_conditions"]
        }

        if analysis["has_signal"] and "signal" in analysis:
            response["signal"] = analysis["signal"]

        return response

    async def create_straddle_trades(self,
                                   symbol: str,
                                   current_price: float,
                                   quantity: float) -> List[Trade]:
        """Create a pair of straddle trades based on current market conditions"""
        try:
            buy_entry, sell_entry = self.strategy.calculate_entry_levels(current_price)

            # Create buy stop order
            buy_tp, buy_sl = self.strategy.calculate_position_params(buy_entry, "UP")
            long_trade = TradeCreate(
                symbol=symbol,
                side="BUY",
                entry_price=buy_entry,
                quantity=quantity,
                take_profit=buy_tp,
                stop_loss=buy_sl,
                status="PENDING",
                order_type="STOP"
            )
            long_trade_db = await trade_crud.create(self.db, obj_in=long_trade)

            # Create sell stop order
            sell_tp, sell_sl = self.strategy.calculate_position_params(sell_entry, "DOWN")
            short_trade = TradeCreate(
                symbol=symbol,
                side="SELL",
                entry_price=sell_entry,
                quantity=quantity,
                take_profit=sell_tp,
                stop_loss=sell_sl,
                status="PENDING",
                order_type="STOP"
            )
            short_trade_db = await trade_crud.create(self.db, obj_in=short_trade)

            # Refresh both trades to ensure consistent state
            await self.db.refresh(long_trade_db)
            await self.db.refresh(short_trade_db)

            # Send notification
            await notification_service.send_straddle_setup_notification(
                symbol=symbol,
                current_price=current_price,
                buy_entry=buy_entry,
                sell_entry=sell_entry,
                quantity=quantity
            )

            logger.info(f"Created straddle trades for {symbol} at {current_price}")
            return [long_trade_db, short_trade_db]

        except Exception as e:
            logger.error(f"Error creating straddle trades: {str(e)}")
            raise

    async def handle_breakout(self,
                            symbol: str,
                            breakout_signal: BreakoutSignal) -> Optional[Trade]:
        """Handle breakout event and manage straddle positions"""
        try:
            # Get pending straddle trades
            pending_trades = await trade_crud.get_multi_by_symbol_and_status(
                self.db, symbol=symbol, status="PENDING"
            )

            if not pending_trades:
                logger.info(f"No pending trades found for symbol {symbol}")
                return None

            # Find matching trades for the breakout direction
            trade_to_activate = None
            trade_to_cancel = None

            for trade in pending_trades:
                if (breakout_signal.direction == "UP" and trade.side == "BUY") or \
                   (breakout_signal.direction == "DOWN" and trade.side == "SELL"):
                    trade_to_activate = trade
                else:
                    trade_to_cancel = trade

            if not trade_to_activate:
                logger.info(f"No matching trade found for {breakout_signal.direction} breakout")
                return None

            # Update the activated trade
            activated_trade = await trade_crud.update(
                self.db,
                db_obj=trade_to_activate,
                obj_in={
                    "status": "OPEN",
                    "entered_at": datetime.utcnow()
                }
            )

            # Update the cancelled trade if it exists
            if trade_to_cancel:
                await trade_crud.update(
                    self.db,
                    db_obj=trade_to_cancel,
                    obj_in={"status": "CANCELLED"}
                )

            # Ensure all relationships are loaded
            await self.db.refresh(activated_trade)

            # Send notification after updates
            try:
                await notification_service.send_breakout_notification(
                    symbol=symbol,
                    direction=breakout_signal.direction,
                    price=breakout_signal.price,
                    confidence=breakout_signal.confidence,
                    indicators={
                        'volume_spike': breakout_signal.volume_spike,
                        'rsi_divergence': breakout_signal.rsi_divergence,
                        'macd_crossover': breakout_signal.macd_crossover
                    }
                )
            except Exception as notify_error:
                logger.error(f"Failed to send notification: {str(notify_error)}")

            # Return the fully loaded trade object
            return activated_trade

        except Exception as e:
            logger.error(f"Error handling breakout: {str(e)}")
            raise

    async def close_straddle_trades(self, symbol: str) -> List[Trade]:
        """Close all open straddle trades for a given symbol"""
        try:
            # Get open trades
            open_trades = await trade_crud.get_multi_by_symbol_and_status(
                self.db, symbol=symbol, status="OPEN"
            )
            closed_trades = []

            for trade in open_trades:
                # Update trade status
                trade.status = "CLOSED"
                trade.closed_at = datetime.utcnow()

                # Get updated trade data
                result = await self.db.execute(
                    select(Trade).filter(Trade.id == trade.id)
                )
                closed_trade = result.scalar_one()
                await self.db.refresh(closed_trade)
                closed_trades.append(closed_trade)

            # Send notifications after updates
            for trade in closed_trades:
                await notification_service.send_position_close_notification(
                    symbol=symbol,
                    side=trade.side,
                    entry_price=trade.entry_price,
                    exit_price=trade.exit_price,
                    pnl=trade.pnl
                )

            logger.info(f"Closed {len(closed_trades)} straddle trades for {symbol}")
            return closed_trades

        except Exception as e:
            logger.error(f"Error closing straddle trades: {str(e)}")
            raise

straddle_service = StraddleService(None)  # Will be initialized with DB session later
