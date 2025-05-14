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
from app.services.helper.heplers import helpers
from app.services.helper.binance_helper import binance_helper
from app.crud.curd_position import position_crud
from app.schemas.position import PositionCreate, PositionUpdate, Position
from app.crud.crud_portfolio import portfolio_crud as portfolio_crud

class StraddleStrategy:
    def __init__(self):
        self.breakout_threshold = settings.DEFAULT_TP_PCT / 100  # 1% breakout threshold
        self.min_confidence = settings.DEFAULT_SL_PCT / 100  # Minimum confidence for breakout signals
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

            try:
                trade_to_activate.status = "OPEN"
                trade_to_activate.entered_at = helpers.get_current_ist_for_db()
                self.db.add(trade_to_activate)
                # Update the activated trade
                # activated_trade = await trade_crud.update(
                #     self.db,
                #     db_obj=trade_to_activate,
                #     obj_in={
                #         "status": "OPEN",
                #         "entered_at": datetime.utcnow()
                #     }
                # )
                logger.info(f"Successfully activated trade {trade_to_activate.id}")

                # Update the cancelled trade if it exists
                if trade_to_cancel:
                    trade_to_cancel.status = "CANCELLED"
                    trade_to_cancel.closed_at = helpers.get_current_ist_for_db()
                    self.db.add(trade_to_cancel)
                    # cancelled_trade = await trade_crud.update(
                    #     self.db,
                    #     db_obj=trade_to_cancel,
                    #     obj_in={
                    #         "status": "CANCELLED",
                    #         "closed_at": datetime.utcnow()
                    #     }
                    # )
                    logger.info(f"Successfully cancelled trade {trade_to_cancel.id}")

            except Exception as update_error:
                logger.error(f"Error updating trades: {str(update_error)}")
                await self.db.rollback()
                raise

            # Send notification after successful updates
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
            await self.db.commit()
            await self.db.refresh(trade_to_activate)
            return trade_to_activate

        except Exception as e:
            logger.error(f"Error handling breakout: {str(e)}")
            raise

    async def close_straddle_trades(self, symbol: str) -> List[Trade]:
        """Close all open straddle trades for a given symbol"""
        try:
            open_trades = await trade_crud.get_multi_by_symbol_and_status(
                self.db, symbol=symbol, status="OPEN"
            )

            if not open_trades:
                logger.info(f"No open trades found for symbol {symbol}")
                return []

            trade_ids_to_process: List[int] = []
            for trade_to_close in open_trades:
                try:
                    # Mark for closure, actual update happens before commit
                    trade_to_close.status = "CLOSED"
                    trade_to_close.closed_at = helpers.get_current_ist_for_db()
                    # self.db.add(trade_to_close) # Not strictly necessary if fetched from this session
                    trade_ids_to_process.append(trade_to_close.id)
                    logger.info(f"Marked trade {trade_to_close.id} for closure.")
                except Exception as trade_error:
                    logger.error(f"Error marking trade {trade_to_close.id} for closure: {str(trade_error)}. Skipping.")
                    continue

            if not trade_ids_to_process:
                logger.info("No trades were successfully marked for closure.")
                return []

            try:
                # Commit all marked changes
                await self.db.commit()
                logger.info(f"Successfully committed closure for trade IDs: {trade_ids_to_process}")
            except Exception as commit_error:
                logger.error(f"Commit failed after marking trades for closure: {str(commit_error)}")
                try:
                    await self.db.rollback()
                    logger.info("Rollback successful after commit failure.")
                except Exception as rollback_error:
                    logger.error(f"Rollback failed after commit failure: {str(rollback_error)}")
                raise # Re-raise the commit error

            # Re-fetch trades to ensure they are in a valid state for further operations (notifications/response)
            final_closed_trades: List[Trade] = []
            for trade_id in trade_ids_to_process:
                try:
                    # Assuming trade_crud.get fetches the object and it's attached to self.db
                    # If trade_crud.get needs to load relationships for notifications/response,
                    # ensure it supports options like selectinload.
                    trade = await trade_crud.get(self.db, id=trade_id)
                    if trade and trade.status == "CLOSED": # Verify it was indeed closed
                        final_closed_trades.append(trade)
                    elif trade:
                        logger.warning(f"Trade {trade_id} found but not in 'CLOSED' status after commit. Status: {trade.status}")
                    else:
                        logger.warning(f"Trade {trade_id} not found after commit.")
                except Exception as fetch_error:
                    logger.error(f"Error fetching trade {trade_id} post-commit: {str(fetch_error)}")
                    continue

            # Send notifications for successfully processed and fetched trades
            for trade_for_notification in final_closed_trades:
                try:
                    await notification_service.send_position_close_notification(
                        symbol=trade_for_notification.symbol,
                        side=trade_for_notification.side,
                        entry_price=trade_for_notification.entry_price,
                        exit_price=trade_for_notification.exit_price,
                        pnl=trade_for_notification.pnl
                    )
                except Exception as notify_error:
                    logger.error(f"Failed to send notification for trade {trade_for_notification.id}: {str(notify_error)}")
                    continue

            logger.info(f"Successfully processed and notified {len(final_closed_trades)} straddle trades for {symbol}.")
            return final_closed_trades

        except Exception as e:
            logger.error(f"Critical error in close_straddle_trades for {symbol}: {str(e)}.")
            # Ensure rollback if an overarching error occurs and session is active
            if self.db.is_active:
                try:
                    await self.db.rollback()
                    logger.info(f"Session rolled back due to critical error in close_straddle_trades: {str(e)}")
                except Exception as final_rollback_error:
                    logger.error(f"Failed to rollback session during critical error handling: {str(final_rollback_error)}")
            raise

    async def get_straddle_positions(self, symbol: str) -> List[Trade]:
        """Get all straddle positions for a given symbol"""
        return await trade_crud.get_multi_by_symbol_and_status(
            self.db, symbol=symbol, status="OPEN"
        )

    async def auto_buy_sell_straddle_start(self, symbol: str) -> List[Trade]:
        """Auto buy or sell straddle based on market conditions"""
        try:
            #get current price
            current_price = await binance_helper.get_price(symbol);

            #get quentity from portfolio
            protfolo_details = await portfolio_crud.get_by_user_and_symbol(self.db, symbol=symbol)
            quantity = protfolo_details.quantity

            buy_entry, sell_entry = self.strategy.calculate_entry_levels(current_price["price"])

            #check if there is a straddle position already
            open_positions = await position_crud.get_by_symbol_and_status(
                self.db, symbol=symbol, status="OPEN"
            )
            if open_positions:
                logger.info(f"Straddle position already exists for {symbol}, skipping auto buy/sell")
                return []

            #create a position
            position = PositionCreate(
                symbol=symbol,
                strategy="TIME_BASED_STRADDLE",  # This is optional if it's the default
                status="OPEN",
                total_quantity=quantity,
                average_entry_price=buy_entry,
                realized_pnl=0,
                unrealized_pnl=0
            )
            position_db = await position_crud.create(self.db, obj_in=position)

            # #get last 100 prices and volumes with 5m interval with market analyzer
            # last_100_prices, last_100_volumes = await MarketAnalyzer.analyze_breakout(symbol, current_price, 100)


            # #analyze market conditions
            # analysis = await self.analyze_market_conditions(symbol, last_100_prices, last_100_volumes)

            await self.db.refresh(position_db)
            return []

        except Exception as e:
            logger.error(f"Error in auto_buy_sell_straddle: {str(e)}")
            raise

    async def auto_buy_sell_straddle_close(self, symbol: str) -> List[Trade]:
        """Auto close straddle position for a given symbol"""
        position = await position_crud.get_by_symbol_and_status(
            self.db, symbol=symbol, status="OPEN"
        )
        if position:
            await self.close_straddle_trades(symbol)
        else:
            logger.info(f"No open straddle position found for {symbol}")
            return []
        return position

    async def auto_buy_sell_straddle_inprogress(self, symbol: str) -> List[Trade]:
        """Auto buy or sell straddle based on market conditions"""
        try:
            #get current price
            current_price = await binance_helper.get_price(symbol)

            #get quentity from portfolio
            protfolo_details = await portfolio_crud.get_by_user_and_symbol(self.db, symbol=symbol)
            quantity = protfolo_details.quantity

            #check if there is a straddle position already
            open_positions = await position_crud.get_position_by_symbol(
                self.db, symbol=symbol
            )
            if open_positions.status == "OPEN":
                await self.create_straddle_trades(symbol, current_price["price"], quantity)

                await self.db.refresh(open_positions)
                logger.info(f"No open straddle position exists for {symbol}, proceeding with auto buy/sell")
                #update the position status to in progress
                open_positions.status = "IN_PROGRESS"
                updated_position = await position_crud.update(
                    self.db,
                    db_obj=open_positions,
                    obj_in={
                        "status": "IN_PROGRESS"
                    }
                )
                await self.db.refresh(updated_position)
                logger.info(f"Updated position status to IN_PROGRESS for {symbol}")
                return updated_position

            #get treas from symbol
            treas = await trade_crud.get_by_symbol(
                self.db, symbol=symbol
            )
            if not treas:
                logger.info(f"No open treas found for {symbol}, proceeding with auto buy/sell")
                return []
            #get current price
            current_price = await binance_helper.get_price(symbol)





            logger.info(f"Straddle position already exists for {symbol}, skipping auto buy/sell")
            return open_positions
        except Exception as e:
            logger.error(f"Error in auto_buy_sell_straddle_working: {str(e)}")
            raise


straddle_service = StraddleService(None)  # Will be initialized with DB session later
