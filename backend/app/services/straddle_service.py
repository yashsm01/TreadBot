from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from app.core.logger import logger
from app.core.config import settings
from app.models.trade import Trade
from app.schemas.trade import TradeCreate
from app.crud.crud_trade import trade as trade_crud
from app.crud.curd_position import position_crud
from app.schemas.position import PositionCreate, PositionUpdate, Position
from app.crud.crud_portfolio import portfolio_crud as portfolio_crud
from app.crud.crud_user_portfolio_summary import user_portfolio_summary_crud
from app.crud.curd_crypto import insert_crypto_data_live
#services
from app.services.helper.heplers import helpers
from app.services.helper.binance_helper import binance_helper
from app.services.helper.market_analyzer import MarketAnalyzer, BreakoutSignal
from app.services.notifications import notification_service
from app.services.market_analyzer import market_analyzer
from app.services.swap_service import swap_service

from app.crud.crud_telegram import telegram_user as telegram_user


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
    # Make straddle_status a class variable so it's shared across all instances
    straddle_status = False
    # Add processing lock flags
    _processing_locks = {}

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
                                   quantity: float,
                                   position_id: int) -> List[Trade]:
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
                order_type="STOP",
                position_id=position_id
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
                order_type="STOP",
                position_id=position_id
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
                self.db, symbol=symbol, status=["PENDING"]
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
                self.db, symbol=symbol, status=["OPEN", "PENDING"]
            )

            if not open_trades:
                logger.info(f"No open or pending trades found for symbol {symbol}")
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
            self.db, symbol=symbol, status=["OPEN"]
        )

    async def auto_buy_sell_straddle_start(self, symbol: str) -> List[Trade]:
        """Auto buy or sell straddle based on market conditions"""
        try:
            #get current price
            current_price = await binance_helper.get_price(symbol);

            #get quentity from portfolio
            protfolo_details = await portfolio_crud.get_by_user_and_symbol(self.db, symbol=symbol)
            quantity = protfolo_details.quantity

            if quantity == 0:
                logger.info(f"No quantity found for {symbol}, skipping auto buy/sell")
                return {
                    "status": "SKIPPED",
                    "reason": "No quantity found",
                    "symbol": symbol,
                    "trades": []
                }

            buy_entry, sell_entry = self.strategy.calculate_entry_levels(current_price["price"])

            #check if there is a straddle position already
            open_positions = await position_crud.get_by_symbol_and_status(
                self.db, symbol=symbol, status=["OPEN"]
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
        try:
            # Get positions with status OPEN or IN_PROGRESS
            position = await position_crud.get_by_symbol_and_status(
                self.db, symbol=symbol, status=["OPEN", "IN_PROGRESS"]
            )

            if not position:
                logger.info(f"No open straddle position found for {symbol}")
                return []

            # Close the trades
            closed_trades = await self.close_straddle_trades(symbol)

            # Update position status
            if position:
                updated_position = await position_crud.update(
                    self.db,
                    db_obj=position,
                    obj_in={"status": "CLOSED"}
                )
                await self.db.refresh(updated_position)
                logger.info(f"Successfully closed position for {symbol}")

            return closed_trades
        except Exception as e:
            logger.error(f"Error closing straddle position for {symbol}: {str(e)}")
            raise

    async def update_portfolio_summary(self, symbol: str) -> Dict:
        """
        Update the portfolio summary after each straddle operation
        This collects data about all assets and stores a snapshot in the user_portfolio_summary table
        """
        try:
            logger.info(f"Updating portfolio summary for symbol {symbol}")

            # Create a new database transaction for portfolio summary operations
            # to isolate it from any potential issues with the previous transaction
            async with AsyncSession(self.db.bind) as isolated_session:
                try:
                    # Get all portfolio assets
                    portfolio_items = await portfolio_crud.get_multi(isolated_session)

                    # Calculate portfolio totals
                    total_value = 0.0
                    total_cost_basis = 0.0
                    crypto_value = 0.0
                    stable_value = 0.0

                    # Prepare assets dict for JSON storage
                    assets_data = {}

                    # Process each asset in portfolio
                    for item in portfolio_items:
                        try:
                            # Get current price
                            # Check if the asset is a stablecoin
                            if item.asset_type == "STABLE":
                                # For stablecoins, use 1.0 as the price since they're pegged to $1
                                current_price = 1.0
                            else:
                                # For other assets, fetch price from Binance
                                price_data = await binance_helper.get_price(item.symbol)
                                current_price = price_data["price"]

                            # Calculate value
                            asset_value = item.quantity * current_price
                            asset_cost = item.quantity * item.avg_buy_price

                            # Add to totals
                            total_value += asset_value
                            total_cost_basis += asset_cost

                            # Categorize as crypto or stable
                            if item.asset_type == "STABLE":
                                stable_value += asset_value
                            else:
                                crypto_value += asset_value

                            # Add to assets data
                            assets_data[item.symbol] = {
                                "symbol": item.symbol,
                                "quantity": item.quantity,
                                "avg_buy_price": item.avg_buy_price,
                                "current_price": current_price,
                                "value": asset_value,
                                "cost_basis": asset_cost,
                                "profit_loss": asset_value - asset_cost,
                                "profit_loss_percentage": ((asset_value - asset_cost) / asset_cost * 100) if asset_cost > 0 else 0,
                                "asset_type": item.asset_type
                            }

                            if not item.asset_type == "STABLE":
                                #Insert Data in Dynamic Table
                                result = await insert_crypto_data_live(self.db, item.symbol);
                                logger.info(f"Insert Crypto data for symbol {item.symbol}")


                        except Exception as asset_error:
                            logger.error(f"Error processing asset {item.symbol}: {str(asset_error)}")
                            continue

                    # Calculate total profit/loss
                    total_profit_loss = total_value - total_cost_basis

                    # Get recent trade count
                    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    trades_today_result = await trade_crud.get_trades_count_since(isolated_session, since=today_start)
                    trades_today = trades_today_result if trades_today_result else 0

                    # Get recent swap count
                    try:
                        from app.crud.crud_swap_transaction import swap_transaction_crud
                        swaps_today_result = await swap_transaction_crud.get_swaps_count_since(isolated_session, since=today_start)
                        swaps_today = swaps_today_result if swaps_today_result else 0
                    except Exception as swap_error:
                        logger.error(f"Error counting swaps: {str(swap_error)}")
                        swaps_today = 0

                    # Get market trend information
                    market_trend = None
                    market_volatility = None

                    try:
                        market_data = await market_analyzer.get_price_data(symbol, interval=settings.TREADING_DEFAULT_INTERVAL, limit=settings.TREADING_DEFAULT_LIMIT)
                        if market_data is not None:
                            recent_prices = market_data['close'].tolist()
                            price_changes = [recent_prices[i] - recent_prices[i-1] for i in range(1, len(recent_prices))]
                            market_trend = "up" if sum(price_changes) > 0 else "down"
                            market_volatility = (max(recent_prices) - min(recent_prices)) / min(recent_prices) if min(recent_prices) > 0 else 0
                    except Exception as market_error:
                        logger.error(f"Error getting market trend: {str(market_error)}")

                    # Get default user ID (use first active user if available)
                    user_id = None
                    try:
                        active_users = await telegram_user.get_active_users(isolated_session)
                        if active_users and len(active_users) > 0:
                            user_id = active_users[0].id
                    except Exception as user_error:
                        logger.error(f"Error getting active user: {str(user_error)}")
                        # Continue with user_id as None

                    # Determine if portfolio is hedged
                    is_hedged = False
                    stable_ratio = 0
                    if (crypto_value + stable_value) > 0:  # Prevent division by zero
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

                    try:
                        # Create portfolio summary record
                        summary = await user_portfolio_summary_crud.create_summary(
                            db=isolated_session,
                            user_id=user_id,
                            total_value=total_value,
                            total_cost_basis=total_cost_basis,
                            total_profit_loss=total_profit_loss,
                            assets=assets_data,
                            crypto_value=crypto_value,
                            stable_value=stable_value,
                            market_trend=market_trend,
                            market_volatility=market_volatility,
                            trades_today=trades_today,
                            swaps_today=swaps_today
                        )

                        logger.info(f"Successfully updated portfolio summary. Total value: ${total_value:.2f}, P/L: ${total_profit_loss:.2f}")

                        # Return summary for reference
                        return {
                            "id": summary.id,
                            "timestamp": summary.timestamp.isoformat(),
                            "total_value": summary.total_value,
                            "total_profit_loss": summary.total_profit_loss,
                            "total_profit_loss_percentage": summary.total_profit_loss_percentage,
                            "crypto_value": summary.crypto_value,
                            "stable_value": summary.stable_value,
                            "daily_change": summary.daily_change,
                            "weekly_change": summary.weekly_change,
                            "monthly_change": summary.monthly_change,
                            "trades_today": summary.trades_today,
                            "swaps_today": summary.swaps_today,
                            "market_trend": summary.market_trend,
                            "risk_level": summary.risk_level
                        }
                    except Exception as summary_error:
                        logger.error(f"Error creating portfolio summary: {str(summary_error)}")
                        # Return a simplified response when the summary table doesn't exist
                        return {
                            "status": "table_error",
                            "message": "Portfolio summary table doesn't exist - run migrations",
                            "total_value": total_value,
                            "total_profit_loss": total_profit_loss
                        }

                except Exception as inner_e:
                    logger.error(f"Error in isolated portfolio summary transaction: {str(inner_e)}")
                    await isolated_session.rollback()
                    raise

        except Exception as e:
            logger.error(f"Error updating portfolio summary: {str(e)}")
            # Return a minimal response on error to prevent cascading failures
            return {
                "status": "error",
                "message": f"Failed to update portfolio summary: {str(e)}"
            }

    async def auto_buy_sell_straddle_inprogress(self, symbol: str) -> Dict:
        """Auto buy or sell straddle based on market conditions"""
        # Check if this symbol is already being processed
        lock_key = f"auto_trading_{symbol}"
        if lock_key in StraddleService._processing_locks and StraddleService._processing_locks[lock_key]:
            logger.info(f"Auto trading for {symbol} is already in progress, skipping")
            return {
                "status": "SKIPPED",
                "reason": "Already processing",
                "symbol": symbol,
                "trades": []
            }

        # Prepare the response object
        response = {
            "status": "IDLE",
            "symbol": symbol,
            "trades": [],
            "metrics": {
                "starting_price": 0,
                "current_price": 0,
                "position_size": 0,
                "current_value": 0,
                "profit_loss": 0,
                "profit_loss_percent": 0,
                "buy_trades": [],
                "sell_trades": []
            },
            "swap_status": {
                "performed": False,
                "from_coin": "",
                "to_coin": "",
                "amount": 0,
                "price": 0
            }
        }

        try:
            # Set the processing lock
            StraddleService._processing_locks[lock_key] = True

            if not StraddleService.straddle_status:
                logger.info(f"Straddle status is disabled, skipping auto buy/sell for {symbol}")
                response["status"] = "DISABLED"
                response["reason"] = "Straddle trading disabled"
                return response

            #check if there is a straddle position already
            open_positions = await position_crud.get_position_by_symbol(
                self.db, symbol=symbol
            )
            if not open_positions:
                logger.info(f"No positions found for {symbol}")
                response["status"] = "NO_POSITION"
                response["reason"] = "No positions found"
                return response

            position_id = open_positions.id
            if open_positions.status == "CLOSED":
                logger.info(f"Straddle position already closed for {symbol}, skipping auto buy/sell")
                response["status"] = "CLOSED"
                response["reason"] = "Position already closed"
                return response

            #get current price
            crypto_details = await binance_helper.get_price(symbol)
            current_price = crypto_details["price"]

            # Update response with current price
            response["metrics"]["current_price"] = current_price
            response["metrics"]["starting_price"] = open_positions.average_entry_price

            #get quentity from portfolio
            protfolo_details = await portfolio_crud.get_by_user_and_symbol(self.db, symbol=symbol)
            quantity = protfolo_details.quantity

            # Update response with position size
            response["metrics"]["position_size"] = quantity
            response["metrics"]["current_value"] = quantity * current_price

            # Get price trend history to make smarter dynamic decisions
            recent_price_data = await market_analyzer.get_price_data(symbol, interval=settings.TREADING_DEFAULT_INTERVAL, limit=settings.TREADING_DEFAULT_LIMIT)
            # Extract close prices
            recent_prices = recent_price_data['close'].tolist()

            # Calculate dynamic thresholds based on recent price data
            price_changes = np.diff(recent_prices) if len(recent_prices) > 1 else []

            PROFIT_THRESHOLD_SMALL, PROFIT_THRESHOLD_MEDIUM, PROFIT_THRESHOLD_LARGE = helpers.calculate_dynamic_profit_threshold(recent_prices, symbol)
            CONSECUTIVE_PRICE_INCREASES_THRESHOLD = helpers.dynamic_consecutive_increase_threshold(price_changes, symbol)
            PRICE_VOLATILITY_THRESHOLD = helpers.calculate_volatility_threshold(recent_prices, symbol)

            # Add the dynamic thresholds to the response
            response["metrics"]["profit_threshold_small"] = PROFIT_THRESHOLD_SMALL
            response["metrics"]["profit_threshold_medium"] = PROFIT_THRESHOLD_MEDIUM
            response["metrics"]["profit_threshold_large"] = PROFIT_THRESHOLD_LARGE
            response["metrics"]["consecutive_threshold"] = CONSECUTIVE_PRICE_INCREASES_THRESHOLD
            response["metrics"]["volatility_threshold"] = PRICE_VOLATILITY_THRESHOLD

            price_direction = "up" if sum(price_changes) > 0 else "down"

            # Update response with trend information
            response["metrics"]["trend_direction"] = price_direction
            response["metrics"]["recent_prices"] = recent_prices[:5]  # Just show the 5 most recent ones

            if open_positions.status == "OPEN":
                trades = await self.create_straddle_trades(symbol, current_price, quantity, position_id)
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

                # Update response
                response["status"] = "INITIATED"
                response["trades"] = [self._trade_to_dict(trade) for trade in trades]
                for trade in trades:
                    if trade.side == "BUY":
                        response["metrics"]["buy_trades"].append(self._trade_to_dict(trade))
                    else:
                        response["metrics"]["sell_trades"].append(self._trade_to_dict(trade))
                return response

            #get trades from symbol
            trades = await trade_crud.get_multi_by_symbol_and_status(
                self.db, symbol=symbol, status=["PENDING"]
            )
            if not trades:
                new_trades = await self.create_straddle_trades(symbol, current_price, quantity, position_id)
                # Update response
                response["status"] = "RECREATED"
                response["trades"] = [self._trade_to_dict(trade) for trade in new_trades]
                for trade in new_trades:
                    if trade.side == "BUY":
                        response["metrics"]["buy_trades"].append(self._trade_to_dict(trade))
                    else:
                        response["metrics"]["sell_trades"].append(self._trade_to_dict(trade))
                return response

            #filter the trades by side buy and status open
            buy_trades = [trade for trade in trades if trade.side == "BUY" and trade.status == "PENDING"]
            sell_trades = [trade for trade in trades if trade.side == "SELL" and trade.status == "PENDING"]

            # Update response with trade information
            response["metrics"]["buy_trades"] = [self._trade_to_dict(trade) for trade in buy_trades]
            response["metrics"]["sell_trades"] = [self._trade_to_dict(trade) for trade in sell_trades]

            if not buy_trades or not sell_trades:
                logger.info(f"Missing buy or sell trades for {symbol}, recreating straddle")
                new_trades = await self.create_straddle_trades(symbol, current_price, quantity, position_id)
                # Update response
                response["status"] = "RECREATED"
                response["trades"] = [self._trade_to_dict(trade) for trade in new_trades]
                # Update buy/sell trades
                response["metrics"]["buy_trades"] = []
                response["metrics"]["sell_trades"] = []
                for trade in new_trades:
                    if trade.side == "BUY":
                        response["metrics"]["buy_trades"].append(self._trade_to_dict(trade))
                    else:
                        response["metrics"]["sell_trades"].append(self._trade_to_dict(trade))
                return response

            # Get price trend history to make smarter decisions
            recent_price_data = await market_analyzer.get_price_data(symbol, interval=settings.TREADING_DEFAULT_INTERVAL, limit=settings.TREADING_DEFAULT_LIMIT)
            # Extract close prices
            recent_prices = recent_price_data['close'].tolist()
            price_changes = [recent_prices[i] - recent_prices[i-1] for i in range(1, len(recent_prices))]
            price_direction = "up" if sum(price_changes) > 0 else "down"

            # Update response with trend information
            response["metrics"]["trend_direction"] = price_direction
            response["metrics"]["recent_prices"] = recent_prices

            # Count consecutive increases/decreases to detect trend strength
            consecutive_same_direction = 1
            for i in range(1, len(price_changes)):
                if (price_changes[i] > 0 and price_changes[i-1] > 0) or (price_changes[i] < 0 and price_changes[i-1] < 0):
                    consecutive_same_direction += 1
                else:
                    break

            # Update response with trend strength
            response["metrics"]["trend_strength"] = consecutive_same_direction

            # Calculate price volatility
            price_volatility = (max(recent_prices) - min(recent_prices)) / min(recent_prices)

            # Update response with volatility
            response["metrics"]["volatility"] = price_volatility

            # Calculate potential profit percentages with safety checks
            try:
                buy_profit_pct = (current_price - buy_trades[0].entry_price) / buy_trades[0].entry_price if buy_trades[0].entry_price > 0 else 0
                sell_profit_pct = (sell_trades[0].entry_price - current_price) / sell_trades[0].entry_price if sell_trades[0].entry_price > 0 else 0

                # Update profit/loss metrics
                if current_price > open_positions.average_entry_price:
                    profit_loss = (current_price - open_positions.average_entry_price) * quantity
                    profit_loss_pct = (current_price - open_positions.average_entry_price) / open_positions.average_entry_price * 100
                else:
                    profit_loss = (open_positions.average_entry_price - current_price) * quantity * -1
                    profit_loss_pct = (open_positions.average_entry_price - current_price) / open_positions.average_entry_price * -100

                response["metrics"]["profit_loss"] = profit_loss
                response["metrics"]["profit_loss_percent"] = profit_loss_pct
                response["metrics"]["buy_profit_percent"] = buy_profit_pct * 100
                response["metrics"]["sell_profit_percent"] = sell_profit_pct * 100
            except Exception as e:
                logger.error(f"Error calculating profit percentages: {str(e)}")
                buy_profit_pct = 0
                sell_profit_pct = 0

            # Determine if we should close positions based on multiple factors
            should_close_buy = False
            should_close_sell = False
            should_swap_to_stable = False
            should_swap_from_stable = False

            # Dynamic threshold based on trend strength and volatility
            dynamic_threshold = PROFIT_THRESHOLD_SMALL
            if consecutive_same_direction >= CONSECUTIVE_PRICE_INCREASES_THRESHOLD:
                dynamic_threshold = PROFIT_THRESHOLD_MEDIUM
            if price_volatility >= PRICE_VOLATILITY_THRESHOLD:
                dynamic_threshold = PROFIT_THRESHOLD_LARGE

            # Update response with threshold
            response["metrics"]["profit_threshold"] = dynamic_threshold

            # Profitable BUY condition - if price has increased enough from our buy entry
            if buy_profit_pct >= dynamic_threshold:
                should_close_buy = True

                # If price is trending up strongly, consider keeping some position
                if price_direction == "up" and consecutive_same_direction >= CONSECUTIVE_PRICE_INCREASES_THRESHOLD:
                    # Only swap half to stablecoin to keep some exposure to further upside
                    should_swap_to_stable = True

            # Profitable SELL condition - if price has decreased enough from our sell entry
            if sell_profit_pct >= dynamic_threshold:
                should_close_sell = True

                # If price is trending down strongly, consider swapping all to stablecoin
                if price_direction == "down" and consecutive_same_direction >= CONSECUTIVE_PRICE_INCREASES_THRESHOLD:
                    should_swap_to_stable = True

            # If price rebounds after a downtrend, buy back in
            if price_direction == "up" and consecutive_same_direction >= 2 and should_swap_to_stable:
                should_swap_from_stable = True

            # Execute the determined strategy
            if (should_close_buy or should_close_sell) and current_price > buy_trades[0].entry_price:
                logger.info(f"Closing positions for {symbol} due to price increase to {current_price} from {buy_trades[0].entry_price}")
                # close old trades
                closed_trades = await self.close_straddle_trades(symbol)
                # create new straddle trades
                new_trades = await self.create_straddle_trades(symbol, current_price, quantity, position_id)

                # If we've made significant profit and price trending up, could hold position
                if buy_profit_pct >= PROFIT_THRESHOLD_MEDIUM and price_direction == "up":
                    logger.info(f"Holding {symbol} position due to strong uptrend, profit: {buy_profit_pct*100:.2f}%")

                # Update response
                response["status"] = "PROFIT_TAKEN"
                response["reason"] = f"Price increased to {current_price} from {buy_trades[0].entry_price}"
                response["metrics"]["action_taken"] = "Closed positions due to price increase"
                response["trades"] = [self._trade_to_dict(trade) for trade in new_trades]
                response["metrics"]["buy_trades"] = []
                response["metrics"]["sell_trades"] = []
                for trade in new_trades:
                    if trade.side == "BUY":
                        response["metrics"]["buy_trades"].append(self._trade_to_dict(trade))
                    else:
                        response["metrics"]["sell_trades"].append(self._trade_to_dict(trade))
                return response

            if (should_close_buy or should_close_sell) and current_price < sell_trades[0].entry_price:
                logger.info(f"Closing positions for {symbol} due to price decrease to {current_price} from {sell_trades[0].entry_price}")
                # close old trades
                closed_trades = await self.close_straddle_trades(symbol)

                # Create new trades at current level
                new_trades = await self.create_straddle_trades(symbol, current_price, quantity, position_id)

                swap_performed = False
                # If price is declining significantly, swap to stablecoin
                if should_swap_to_stable:
                    logger.info(f"Swapping {symbol} to stablecoin due to downtrend, profit: {sell_profit_pct*100:.2f}%")

                    # Determine swap amount based on trend severity
                    swap_percentage = 0.5  # Default 50%
                    if consecutive_same_direction >= 4 or price_volatility >= 0.04:
                        swap_percentage = 1.0  # Swap 100% in severe downtrends

                    swap_amount = quantity * swap_percentage
                    if swap_amount > 0:
                        swap_result = await swap_service.swap_symbol_stable_coin(symbol, swap_amount, current_price)
                        swap_performed = True

                        # Update swap status
                        response["swap_status"]["performed"] = True
                        response["swap_status"]["from_coin"] = symbol
                        response["swap_status"]["to_coin"] = "USDT"  # Assuming stablecoin is USDT
                        response["swap_status"]["amount"] = swap_amount
                        response["swap_status"]["price"] = current_price

                # If we've started seeing a reversal after swapping to stable, consider swapping back
                if should_swap_from_stable and consecutive_same_direction >= 3:
                    # Get available stablecoins
                    stable_coin_data = await binance_helper.get_best_stable_coin()
                    stable_coin = stable_coin_data["best_stable"]

                    # Check if we have this stablecoin in portfolio
                    stable_portfolio = await portfolio_crud.get_by_user_and_symbol(self.db, symbol=stable_coin)

                    if stable_portfolio and stable_portfolio.quantity > 0:
                        # Calculate amount to swap back - be conservative
                        swap_back_percentage = 0.3  # Start with 30%
                        if consecutive_same_direction >= 5:  # Strong reversal
                            swap_back_percentage = 0.5  # Increase to 50%

                        swap_amount = stable_portfolio.quantity * swap_back_percentage
                        if swap_amount > 0:
                            logger.info(f"Swapping back from {stable_coin} to {symbol} due to uptrend reversal")
                            swap_result = await swap_service.swap_stable_coin_symbol(stable_coin, symbol, swap_amount)
                            swap_performed = True

                            # Update swap status
                            response["swap_status"]["performed"] = True
                            response["swap_status"]["from_coin"] = stable_coin
                            response["swap_status"]["to_coin"] = symbol
                            response["swap_status"]["amount"] = swap_amount
                            response["swap_status"]["price"] = current_price

                # Update response
                response["status"] = "PROFIT_TAKEN"
                if swap_performed:
                    response["reason"] = f"Price decreased to {current_price} and performed swap"
                else:
                    response["reason"] = f"Price decreased to {current_price} from {sell_trades[0].entry_price}"
                response["metrics"]["action_taken"] = "Closed positions due to price decrease"
                response["trades"] = [self._trade_to_dict(trade) for trade in new_trades]
                response["metrics"]["buy_trades"] = []
                response["metrics"]["sell_trades"] = []
                for trade in new_trades:
                    if trade.side == "BUY":
                        response["metrics"]["buy_trades"].append(self._trade_to_dict(trade))
                    else:
                        response["metrics"]["sell_trades"].append(self._trade_to_dict(trade))
                return response

            logger.info(f"Straddle position already exists for {symbol}, monitoring for opportunities")
            # Update response
            response["status"] = "MONITORING"
            response["trades"] = [self._trade_to_dict(trade) for trade in trades]

            # At the end of the function, before returning and after all operations are complete,
            # update the portfolio summary
            try:
                portfolio_summary = await self.update_portfolio_summary(symbol)
                # Add portfolio summary to response
                response["portfolio_summary"] = portfolio_summary
            except Exception as summary_error:
                logger.error(f"Error updating portfolio summary: {str(summary_error)}")
                # Don't fail the entire operation if portfolio summary update fails

            return response

        except Exception as e:
            logger.error(f"Error in auto_buy_sell_straddle_inprogress: {str(e)}")
            # Update response with error information
            response["status"] = "ERROR"
            response["error"] = str(e)
            return response
        finally:
            # Release the processing lock
            StraddleService._processing_locks[lock_key] = False

    def _trade_to_dict(self, trade):
        """Convert a Trade object to a dictionary for response"""
        return {
            "id": trade.id if hasattr(trade, 'id') else None,
            "symbol": trade.symbol,
            "side": trade.side,
            "entry_price": trade.entry_price,
            "quantity": trade.quantity,
            "take_profit": trade.take_profit,
            "stop_loss": trade.stop_loss,
            "status": trade.status,
            "order_type": trade.order_type,
            "entered_at": trade.entered_at.isoformat() if trade.entered_at else None,
            "closed_at": trade.closed_at.isoformat() if trade.closed_at else None,
            "pnl": trade.pnl
        }

    async def change_straddle_status(self):
        # Use class name to access the class variable
        StraddleService.straddle_status = not StraddleService.straddle_status
        logger.info(f"Straddle status changed to {StraddleService.straddle_status}")
        return StraddleService.straddle_status

straddle_service = StraddleService(None)  # Will be initialized with DB session later
