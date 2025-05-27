from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import math
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

    def calculate_volatility(self, prices: List[float]) -> float:
        """Calculate volatility as the standard deviation of log returns."""
        if len(prices) < 2:
            return 0.0
        log_returns = np.diff(np.log(prices))
        return float(np.std(log_returns))

    def calculate_entry_levels_dynamic(
        self,
        current_price: float,
        short_vol: float,
        medium_vol: float,
        long_vol: float
    ) -> dict:
        """
        Calculate dynamic entry levels for straddle based on volatility with enhanced precision.

        Features:
        - Adaptive volatility scaling based on market conditions
        - 1:3 buy/sell ratio for each timeframe
        - 1:2:3 ratio between short/medium/long timeframes
        - Intelligent clamping with market-aware bounds
        - Comprehensive return data including all calculated percentages

        Args:
            current_price: Current market price
            short_vol: Short-term volatility (e.g., 5m intervals)
            medium_vol: Medium-term volatility (e.g., 1h intervals)
            long_vol: Long-term volatility (e.g., 4h intervals)

        Returns:
            dict: Comprehensive entry levels with metadata
        """
        try:
            # Input validation
            if current_price <= 0:
                raise ValueError("Current price must be positive")

            # Normalize volatilities to prevent extreme values
            volatilities = [short_vol, medium_vol, long_vol]
            avg_vol = sum(volatilities) / len(volatilities) if volatilities else 0.01

            # Use the most conservative (lowest) volatility as base to prevent over-leveraging
            base_vol = min(volatilities) if all(v > 0 for v in volatilities) else avg_vol

            # Adaptive scaling factor based on overall market volatility
            if avg_vol > 0.05:  # High volatility market (>5%)
                scale_factor = 0.8  # Be more conservative
                min_pct = 0.002  # 0.2%
                max_pct = 0.015  # 1.5%
            elif avg_vol > 0.02:  # Medium volatility market (2-5%)
                scale_factor = 1.0  # Normal scaling
                min_pct = 0.003  # 0.3%
                max_pct = 0.02   # 2%
            else:  # Low volatility market (<2%)
                scale_factor = 1.2  # Be more aggressive
                min_pct = 0.005  # 0.5%
                max_pct = 0.03   # 3%

            # Calculate base percentage with adaptive scaling
            base_pct = base_vol * scale_factor

            # Ensure minimum viable percentage
            if base_pct < min_pct:
                base_pct = min_pct

            # Calculate multipliers to enforce 1:2:3 ratio between timeframes
            short_pct = base_pct
            medium_pct = base_pct * 2
            long_pct = base_pct * 3

            # Intelligent clamping with progressive limits
            short_pct = max(min(short_pct, max_pct), min_pct)
            medium_pct = max(min(medium_pct, max_pct * 1.5), min_pct * 1.5)
            long_pct = max(min(long_pct, max_pct * 2), min_pct * 2)

            # Calculate buy/sell percentages with 1:3 ratio for each timeframe
            # Buy side (more conservative)
            short_buy_pct = short_pct
            medium_buy_pct = medium_pct
            long_buy_pct = long_pct

            # Sell side (more aggressive, 3x the buy percentage)
            short_sell_pct = max(min(short_pct * 3, max_pct * 1.2), min_pct)
            medium_sell_pct = max(min(medium_pct * 3, max_pct * 1.8), min_pct * 1.5)
            long_sell_pct = max(min(long_pct * 3, max_pct * 2.4), min_pct * 2)

            # Calculate actual entry prices
            entries = {
                "short": {
                    "buy": round(current_price * (1 + short_buy_pct), 8),
                    "sell": round(current_price * (1 - short_sell_pct), 8),
                    "buy_pct": round(short_buy_pct * 100, 4),
                    "sell_pct": round(short_sell_pct * 100, 4),
                    "volatility": round(short_vol * 100, 4)
                },
                "medium": {
                    "buy": round(current_price * (1 + medium_buy_pct), 8),
                    "sell": round(current_price * (1 - medium_sell_pct), 8),
                    "buy_pct": round(medium_buy_pct * 100, 4),
                    "sell_pct": round(medium_sell_pct * 100, 4),
                    "volatility": round(medium_vol * 100, 4)
                },
                "long": {
                    "buy": round(current_price * (1 + long_buy_pct), 8),
                    "sell": round(current_price * (1 - long_sell_pct), 8),
                    "buy_pct": round(long_buy_pct * 100, 4),
                    "sell_pct": round(long_sell_pct * 100, 4),
                    "volatility": round(long_vol * 100, 4)
                },
                "metadata": {
                    "current_price": current_price,
                    "base_volatility": round(base_vol * 100, 4),
                    "average_volatility": round(avg_vol * 100, 4),
                    "scale_factor": scale_factor,
                    "market_condition": "high_vol" if avg_vol > 0.05 else "medium_vol" if avg_vol > 0.02 else "low_vol",
                    "min_pct_used": round(min_pct * 100, 4),
                    "max_pct_used": round(max_pct * 100, 4),
                    "calculation_timestamp": datetime.now().isoformat()
                }
            }

            # Validation: Ensure buy > current > sell for all timeframes
            for timeframe in ["short", "medium", "long"]:
                if entries[timeframe]["buy"] <= current_price:
                    entries[timeframe]["buy"] = current_price * (1 + min_pct)
                    entries[timeframe]["buy_pct"] = round(min_pct * 100, 4)

                if entries[timeframe]["sell"] >= current_price:
                    entries[timeframe]["sell"] = current_price * (1 - min_pct)
                    entries[timeframe]["sell_pct"] = round(min_pct * 100, 4)

            return entries

        except Exception as e:
            # Fallback to conservative static values if calculation fails
            fallback_pct = 0.01  # 1%
            return {
                "short": {
                    "buy": current_price * (1 + fallback_pct),
                    "sell": current_price * (1 - fallback_pct * 2),
                    "buy_pct": fallback_pct * 100,
                    "sell_pct": fallback_pct * 2 * 100,
                    "volatility": 0
                },
                "medium": {
                    "buy": current_price * (1 + fallback_pct * 1.5),
                    "sell": current_price * (1 - fallback_pct * 3),
                    "buy_pct": fallback_pct * 1.5 * 100,
                    "sell_pct": fallback_pct * 3 * 100,
                    "volatility": 0
                },
                "long": {
                    "buy": current_price * (1 + fallback_pct * 2),
                    "sell": current_price * (1 - fallback_pct * 4),
                    "buy_pct": fallback_pct * 2 * 100,
                    "sell_pct": fallback_pct * 4 * 100,
                    "volatility": 0
                },
                "metadata": {
                    "current_price": current_price,
                    "error": str(e),
                    "fallback_used": True,
                    "calculation_timestamp": datetime.now().isoformat()
                }
            }

    def calculate_entry_levels(self, current_price: float) -> Tuple[float, float]:
        """Calculate entry levels for straddle"""
        buy_entry = current_price * (1 + self.breakout_threshold)
        sell_entry = current_price * (1 - self.min_confidence)
        return buy_entry, sell_entry

    def calculate_position_params(self, entry_price: float, short_buy_pct: float, short_sell_pct: float, direction: str) -> Tuple[float, float]:
        """Calculate TP and SL as percentage-based price deltas."""

        if entry_price <= 0:
            raise ValueError("Entry price must be greater than 0.")

        direction = direction.upper()
        if direction not in ("UP", "DOWN"):
            raise ValueError("Direction must be 'UP' or 'DOWN'.")

        tp_pct = short_buy_pct  # Example: 0.01 for 1%
        sl_pct = short_sell_pct  # Example: 0.01 for 1%

        tp_amount = (entry_price * tp_pct)/ 100
        sl_amount = (entry_price * sl_pct)/ 100

        if direction == "UP":
            take_profit = entry_price + tp_amount
            stop_loss = entry_price - sl_amount
        else:  # DOWN (short)
            take_profit = entry_price - tp_amount
            stop_loss = entry_price + sl_amount

        return take_profit, stop_loss

    def is_good_buy_entry(self, price_direction, short_term_changes, relative_volume, price, support_levels, resistance_levels):
        # 1. Momentum Check
        # Add additional buying conditions using log returns:
        # Positive momentum in recent log returns
        positive_momentum = np.sum(short_term_changes[-20:]) > 0

        # 2. Increasing trading volume spike
        volume_confirms = relative_volume > 1.1

        # 3.  Current price is above a key support level
        near_support = any(price > s for s in support_levels)

        # 4. Resistance Safe: Not approaching immediate resistance
        # not_near_resistance = all(price < r * 0.95 for r in resistance_levels)
        not_near_resistance = True
        return (
            positive_momentum and
            volume_confirms and
            near_support and
            not_near_resistance
        )
class StraddleService:
    # Make straddle_status a class variable so it's shared across all instances
    straddle_status = True
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
            # Validate inputs
            if quantity <= 0:
                raise ValueError(f"Invalid quantity {quantity} for {symbol}. Quantity must be greater than 0.")

            if current_price <= 0:
                raise ValueError(f"Invalid current price {current_price} for {symbol}. Price must be greater than 0.")

            if position_id is None or position_id <= 0:
                raise ValueError(f"Invalid position_id {position_id} for {symbol}. Position ID must be provided and greater than 0.")

            # Validate if quantity is sufficient for trading
            if not self.validate_trade_quantity(symbol, quantity, current_price):
                min_quantity = self.get_minimum_trade_quantity(symbol, current_price)
                trade_value = quantity * current_price
                raise ValueError(f"Quantity {quantity} insufficient for {symbol}. "
                               f"Minimum quantity: {min_quantity}, minimum trade value: $10.00. "
                               f"Current trade value: ${trade_value:.2f}")

            # Fetch historical close prices from Binance for volatility calculation
            price_history_result = await binance_helper.get_dynamic_price_history(symbol, interval="5m", intervals=50)
            close_prices = [entry["close"] for entry in price_history_result["data"]["history"]]

            short_term_prices = close_prices
            medium_term_prices = close_prices
            long_term_prices = close_prices

            short_vol = self.strategy.calculate_volatility(short_term_prices)
            medium_vol = self.strategy.calculate_volatility(medium_term_prices)
            long_vol = self.strategy.calculate_volatility(long_term_prices)

            entry_levels = self.strategy.calculate_entry_levels_dynamic(
                current_price, short_vol, medium_vol, long_vol
            )

            buy_entry = entry_levels['short']['buy']
            sell_entry = entry_levels['short']['sell']
            short_buy_pct = entry_levels['short']['buy_pct']
            short_sell_pct = entry_levels['short']['sell_pct']

            # Create buy stop order
            buy_tp, buy_sl = self.strategy.calculate_position_params(buy_entry,short_buy_pct,short_sell_pct, "UP")
            long_trade = TradeCreate(
                symbol=symbol,
                side="BUY",
                current_price=current_price,
                entry_price=buy_entry,
                quantity=quantity,
                take_profit=buy_tp,
                stop_loss=buy_sl,
                status="PENDING",
                order_type="STOP",
                buy_pct= short_buy_pct,
                sell_pct= short_sell_pct,
                position_id=position_id
            )
            long_trade_db = await trade_crud.create(self.db, obj_in=long_trade)

            # Create sell stop order
            sell_tp, sell_sl = self.strategy.calculate_position_params(sell_entry,short_buy_pct,short_sell_pct, "DOWN")
            short_trade = TradeCreate(
                symbol=symbol,
                side="SELL",
                current_price=current_price,
                entry_price=sell_entry,
                quantity=quantity,
                take_profit=sell_tp,
                stop_loss=sell_sl,
                status="PENDING",
                order_type="STOP",
                buy_pct= short_buy_pct,
                sell_pct= short_sell_pct,
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

            logger.info(f"Created straddle trades for {symbol} at {current_price} with quantity {quantity}")
            return [long_trade_db, short_trade_db]

        except ValueError as ve:
            logger.error(f"Validation error creating straddle trades: {str(ve)}")
            raise
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

    async def auto_buy_sell_straddle_start(self, symbol: str, max_trade_limit: float,trade_amount: float) -> List[Trade]:
        """Auto buy or sell straddle based on market conditions"""
        try:
            #get current price
            current_price = await binance_helper.get_price(symbol);

            #get quentity from portfolio
            protfolo_details = await portfolio_crud.get_by_user_and_symbol(self.db, symbol=symbol)

            # Handle case where portfolio entry doesn't exist
            if not protfolo_details:
                logger.warning(f"No portfolio entry found for {symbol}, treating as zero quantity")
                quantity = 0
            else:
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
                unrealized_pnl=0,
                max_trade_limit=max_trade_limit,
                trade_amount=trade_amount
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
            await self.db.refresh(position)
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

    async def update_portfolio_summary(self, symbol: str, update_crypto: bool = True, include_market_metrics: bool = False) -> Dict:
        """
        Update the portfolio summary after each straddle operation
        This collects data about all assets and stores a snapshot in the user_portfolio_summary table

        Args:
            symbol: The trading symbol that triggered the update
            update_crypto: Whether to update crypto data in the dynamic table
            include_market_metrics: Whether to include additional market metrics for intraday analysis
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

                    # Track market cap weighted metrics
                    total_market_cap = 0.0
                    weighted_volatility = 0.0
                    weighted_volume = 0.0

                    # For intraday analytics, track additional metrics
                    intraday_metrics = {}

                    # Process each asset in portfolio
                    for item in portfolio_items:
                        try:
                            # Get current price
                            # Check if the asset is a stablecoin
                            if item.asset_type == "STABLE":
                                # For stablecoins, use 1.0 as the price since they're pegged to $1
                                current_price = 1.0
                                price_change_24h = 0.0
                                volume_24h = 0.0
                            else:
                                # For other assets, fetch enhanced price data from Binance
                                price_data = await binance_helper.get_enhanced_price_data(item.symbol)
                                current_price = price_data.get("price", 0.0)
                                price_change_24h = price_data.get("price_change_percentage_24h", 0.0)
                                volume_24h = price_data.get("volume_24h", 0.0)

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
                                # For non-stablecoins, add to market cap weighting
                                total_market_cap += asset_value

                                # For intraday analysis, fetch and store additional metrics
                                if include_market_metrics and item.asset_type != "STABLE":
                                    try:
                                        # Get short-term data for intraday analysis
                                        short_term_data = await market_analyzer.get_price_data(
                                            item.symbol,
                                            interval="5m",
                                            limit=60
                                        )

                                        if short_term_data is not None:
                                            # Calculate intraday volatility
                                            short_term_prices = short_term_data['close'].tolist()
                                            intraday_vol = helpers.calculate_intraday_volatility(short_term_prices)

                                            # Calculate relative volume
                                            short_term_volumes = short_term_data['volume'].tolist()
                                            rel_volume = helpers.calculate_relative_volume(short_term_volumes)

                                            # Detect intraday patterns
                                            pattern = helpers.detect_intraday_pattern(
                                                short_term_data['open'].tolist(),
                                                short_term_data['high'].tolist(),
                                                short_term_data['low'].tolist(),
                                                short_term_data['close'].tolist(),
                                                short_term_volumes
                                            )

                                            # Get support/resistance levels
                                            support_levels, resistance_levels = helpers.find_support_resistance_levels(
                                                short_term_data['high'].tolist(),
                                                short_term_data['low'].tolist(),
                                                current_price,
                                                num_levels=2
                                            )

                                            # Store intraday metrics for this asset
                                            intraday_metrics[item.symbol] = {
                                                "intraday_volatility": intraday_vol,
                                                "relative_volume": rel_volume,
                                                "pattern": pattern,
                                                "support_levels": support_levels,
                                                "resistance_levels": resistance_levels,
                                                "recent_price_action": short_term_prices[-5:],
                                                "price_change_24h": price_change_24h
                                            }

                                            # Contribute to weighted metrics
                                            weighted_volatility += intraday_vol * asset_value
                                            weighted_volume += rel_volume * asset_value
                                    except Exception as metrics_error:
                                        logger.error(f"Error calculating intraday metrics for {item.symbol}: {str(metrics_error)}")

                            # Add to assets data with enhanced information
                            profit_loss = asset_value - asset_cost
                            profit_loss_pct = ((asset_value - asset_cost) / asset_cost * 100) if asset_cost > 0 else 0

                            assets_data[item.symbol] = {
                                "symbol": item.symbol,
                                "quantity": item.quantity,
                                "avg_buy_price": item.avg_buy_price,
                                "current_price": current_price,
                                "value": asset_value,
                                "cost_basis": asset_cost,
                                "profit_loss": profit_loss,
                                "profit_loss_percentage": profit_loss_pct,
                                "asset_type": item.asset_type,
                                "price_change_24h": price_change_24h,
                                "volume_24h": volume_24h,
                                "allocation_percentage": (asset_value / total_value * 100) if total_value > 0 else 0,
                                "last_updated": datetime.now().isoformat()
                            }

                            if not item.asset_type == "STABLE" and update_crypto:
                                #Insert Data in Dynamic Table
                                result = await insert_crypto_data_live(self.db, item.symbol)
                                logger.info(f"Insert Crypto data for symbol {item.symbol}")

                        except Exception as asset_error:
                            logger.error(f"Error processing asset {item.symbol}: {str(asset_error)}")
                            continue

                    # Calculate total profit/loss
                    total_profit_loss = total_value - total_cost_basis

                    # Calculate portfolio-wide intraday metrics if we have market cap data
                    if total_market_cap > 0:
                        weighted_volatility = weighted_volatility / total_market_cap
                        weighted_volume = weighted_volume / total_market_cap

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

                    # Enhanced metrics for intraday trading
                    if include_market_metrics:
                        # Adjust risk level based on intraday volatility
                        if weighted_volatility > 0.02:
                            risk_level = min(5, risk_level + 1)

                        # Generate trading recommendations based on portfolio and market conditions
                        trading_recommendations = self._generate_trading_recommendations(
                            assets_data,
                            intraday_metrics,
                            stable_ratio,
                            market_trend
                        )
                    else:
                        trading_recommendations = []

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

                        # Create enhanced response with intraday metrics if requested
                        response = {
                            "id": summary.id,
                            "timestamp": summary.timestamp.isoformat(),
                            "total_value": summary.total_value,
                            "total_profit_loss": summary.total_profit_loss,
                            "total_profit_loss_percentage": summary.total_profit_loss_percentage,
                            "crypto_value": summary.crypto_value,
                            "stable_value": summary.stable_value,
                            "stable_ratio": stable_ratio * 100,  # Convert to percentage
                            "daily_change": summary.daily_change,
                            "weekly_change": summary.weekly_change,
                            "monthly_change": summary.monthly_change,
                            "trades_today": summary.trades_today,
                            "swaps_today": summary.swaps_today,
                            "market_trend": summary.market_trend,
                            "risk_level": summary.risk_level,
                            "last_updated": datetime.now().isoformat()
                        }

                        # Add intraday metrics if requested
                        if include_market_metrics:
                            response["intraday_metrics"] = {
                                "portfolio_volatility": weighted_volatility,
                                "portfolio_volume_profile": weighted_volume,
                                "asset_metrics": intraday_metrics,
                                "trading_recommendations": trading_recommendations
                            }

                        return response
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

    def _generate_trading_recommendations(self, assets_data, intraday_metrics, stable_ratio, market_trend):
        """
        Generate trading recommendations based on portfolio analysis and market conditions

        Args:
            assets_data: Dictionary of asset data from portfolio
            intraday_metrics: Dictionary of intraday metrics for each asset
            stable_ratio: Ratio of stablecoins in portfolio
            market_trend: Overall market trend (up/down)

        Returns:
            List of trading recommendations
        """
        recommendations = []

        try:
            # 1. Check if we're overexposed to crypto (low stable ratio during downtrend)
            if market_trend == "down" and stable_ratio < 0.3:
                recommendations.append({
                    "type": "HEDGE",
                    "action": "INCREASE_STABLE",
                    "reason": "Low stablecoin allocation during market downtrend",
                    "suggestion": "Consider swapping some crypto to stablecoins",
                    "priority": "HIGH"
                })

            # 2. Check if we're underexposed to crypto (high stable ratio during uptrend)
            elif market_trend == "up" and stable_ratio > 0.6:
                recommendations.append({
                    "type": "ALLOCATION",
                    "action": "INCREASE_CRYPTO",
                    "reason": "High stablecoin allocation during market uptrend",
                    "suggestion": "Consider deploying stablecoins into crypto assets",
                    "priority": "MEDIUM"
                })

            # 3. Check for high volatility assets that might need attention
            for symbol, metrics in intraday_metrics.items():
                # Skip if no metrics or not a real crypto asset
                if not metrics or symbol not in assets_data or assets_data[symbol]["asset_type"] == "STABLE":
                    continue

                # Get asset data
                asset = assets_data[symbol]

                # Check for bearish patterns with large holdings
                if (metrics.get("pattern") in ["double_top", "head_shoulders", "bearish_trend"] and
                    asset["allocation_percentage"] > 15 and  # Significant allocation
                    metrics.get("price_change_24h", 0) < -5):  # Already declining

                    recommendations.append({
                        "type": "RISK_MANAGEMENT",
                        "action": "REDUCE_EXPOSURE",
                        "symbol": symbol,
                        "reason": f"Bearish pattern detected for {symbol} with large allocation",
                        "suggestion": "Consider reducing position size",
                        "priority": "HIGH",
                        "pattern": metrics.get("pattern")
                    })

                # Check for bullish patterns in underweighted assets
                elif (metrics.get("pattern") in ["double_bottom", "inverse_head_shoulders", "bullish_trend"] and
                      asset["allocation_percentage"] < 5 and  # Small allocation
                      metrics.get("relative_volume", 0) > 1.2):  # Higher than average volume

                    recommendations.append({
                        "type": "OPPORTUNITY",
                        "action": "INCREASE_EXPOSURE",
                        "symbol": symbol,
                        "reason": f"Bullish pattern detected for {symbol} with small allocation",
                        "suggestion": "Consider increasing position size",
                        "priority": "MEDIUM",
                        "pattern": metrics.get("pattern")
                    })

                # Check for assets near support/resistance
                support_levels = metrics.get("support_levels", [])
                resistance_levels = metrics.get("resistance_levels", [])
                current_price = asset["current_price"]

                # Near resistance - potential exit point
                for level in resistance_levels:
                    if 0.97 <= current_price / level <= 1.03:  # Within 3% of resistance
                        recommendations.append({
                            "type": "TECHNICAL",
                            "action": "CONSIDER_PROFIT_TAKING",
                            "symbol": symbol,
                            "reason": f"{symbol} approaching resistance at {level:.2f}",
                            "suggestion": "Consider taking partial profits",
                            "priority": "MEDIUM"
                        })
                        break

                # Near support - potential entry point
                for level in support_levels:
                    if 0.97 <= current_price / level <= 1.03:  # Within 3% of support
                        recommendations.append({
                            "type": "TECHNICAL",
                            "action": "CONSIDER_ENTRY",
                            "symbol": symbol,
                            "reason": f"{symbol} approaching support at {level:.2f}",
                            "suggestion": "Consider adding to position",
                            "priority": "MEDIUM"
                        })
                        break

            # Sort recommendations by priority
            priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
            recommendations.sort(key=lambda x: priority_order.get(x.get("priority", "LOW"), 3))

            return recommendations

        except Exception as e:
            logger.error(f"Error generating trading recommendations: {str(e)}")
            return []

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
                "sell_trades": [],
                "profit_threshold_small": 0,
                "profit_threshold_medium": 0,
                "profit_threshold_large": 0,
                "consecutive_threshold": 0,
                "volatility_threshold": 0
            },
            "swap_status": {
                "performed": False,
                "swap_transaction_id": None,
                "from_coin": "",
                "to_coin": "",
                "amount": 0,
                "price": 0
            },
            "market_analysis": {
                "short_term_trend": "",
                "intraday_pattern": "",
                "support_levels": [],
                "resistance_levels": [],
                "volume_profile": ""
            },
            "suggestions": []
        }

        try:
            #set the db for swap service
            swap_service.db = self. db
            # Set the processing lock
            StraddleService._processing_locks[lock_key] = True

            # Initialize zero quantity mode flag
            zero_quantity_mode = False

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
            max_trade_limit = open_positions.max_trade_limit
            trade_amount = open_positions.trade_amount
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

            # Handle case where portfolio entry doesn't exist
            if not protfolo_details:
                logger.warning(f"No portfolio entry found for {symbol}, treating as zero quantity")
                quantity = 0
            else:
                quantity = protfolo_details.quantity

            # Validate quantity before proceeding
            if quantity <= 0:
                logger.warning(f"Zero quantity found for {symbol}, but checking for stablecoin swap opportunities")
                response["status"] = "ZERO_QUANTITY_MONITORING"
                response["reason"] = f"Zero quantity for {symbol}, monitoring for swap opportunities from stablecoins"
                response["metrics"]["position_size"] = quantity
                response["metrics"]["current_value"] = 0

                # Don't return early - continue to check for stablecoin swap opportunities
                # Set a flag to indicate we're in zero-quantity mode
                zero_quantity_mode = True
            else:
                # Additional validation for minimum trading requirements when we have quantity
                if not self.validate_trade_quantity(symbol, quantity, current_price):
                    min_quantity = self.get_minimum_trade_quantity(symbol, current_price)
                    trade_value = quantity * current_price
                    min_trade_value = 10.0

                    logger.warning(f"Quantity {quantity} insufficient for trading {symbol}")
                    response["status"] = "INSUFFICIENT_QUANTITY"
                    response["reason"] = f"Quantity {quantity} insufficient for trading. Minimum: {min_quantity}, trade value: ${trade_value:.2f}"
                    response["metrics"]["position_size"] = quantity
                    response["metrics"]["current_value"] = trade_value
                    response["metrics"]["minimum_quantity"] = min_quantity
                    response["metrics"]["minimum_trade_value"] = min_trade_value
                    response["suggestions"] = [
                        f"Minimum quantity required: {min_quantity}",
                        f"Minimum trade value required: ${min_trade_value}",
                        f"Current trade value: ${trade_value:.2f}",
                        "Consider increasing your position size"
                    ]
                    return response
                zero_quantity_mode = False

            # Update response with position size (only if not in zero quantity mode)
            if not zero_quantity_mode:
                response["metrics"]["position_size"] = quantity
                response["metrics"]["current_value"] = quantity * current_price

            # Get enhanced market data for intraday analysis (include volume, OHLC, and more candlesticks)
            # Use shorter intervals for more granular intraday analysis
            short_interval = "5m"  # 5-minute intervals for short-term trends
            medium_interval = "15m"  # 15-minute intervals for medium-term trends
            long_interval = settings.TREADING_DEFAULT_INTERVAL  # Keep original interval for consistency

            # Get historical price data with different timeframes
            short_term_data = await market_analyzer.get_price_data(symbol, interval=short_interval, limit=60)  # Last 5 hours
            medium_term_data = await market_analyzer.get_price_data(symbol, interval=medium_interval, limit=48)  # Last 12 hours
            long_term_data = await market_analyzer.get_price_data(symbol, interval=long_interval, limit=settings.TREADING_DEFAULT_LIMIT)

            # Extract close prices and volumes
            recent_prices = long_term_data['close'].tolist()
            recent_volumes = long_term_data['volume'].tolist()
            short_term_prices = short_term_data['close'].tolist()
            short_term_volumes = short_term_data['volume'].tolist()

            # Calculate intraday price changes using log returns instead of simple returns
            # Log returns are more accurate for compounding and large price movements
            price_changes = np.diff(np.log(recent_prices)) if len(recent_prices) > 1 else []
            short_term_changes = np.diff(np.log(short_term_prices)) if len(short_term_prices) > 1 else []

            # Enhanced market analysis for intraday trading
            # Identify key support and resistance levels
            support_levels, resistance_levels = helpers.find_support_resistance_levels(
                long_term_data['high'].tolist(),
                long_term_data['low'].tolist(),
                current_price,
                num_levels=3
            )

            # Calculate volume profile to detect accumulation/distribution
            volume_profile = helpers.analyze_volume_profile(recent_prices, recent_volumes)

            # Detect intraday patterns
            intraday_pattern = helpers.detect_intraday_pattern(
                short_term_data['open'].tolist(),
                short_term_data['high'].tolist(),
                short_term_data['low'].tolist(),
                short_term_data['close'].tolist(),
                short_term_volumes
            )

            # Determine time of day effect (some hours have predictable patterns)
            current_hour = datetime.now().hour
            time_of_day_factor = helpers.get_time_of_day_factor(current_hour, symbol)

            # Enhanced volatility metrics for intraday
            intraday_volatility = helpers.calculate_intraday_volatility(short_term_prices)

            # Calculate relative volume compared to average
            relative_volume = helpers.calculate_relative_volume(recent_volumes)

            # Update response with enhanced market analysis
            response["market_analysis"]["short_term_trend"] = "up" if sum(short_term_changes[-10:]) > 0 else "down"
            response["market_analysis"]["intraday_pattern"] = intraday_pattern
            response["market_analysis"]["support_levels"] = support_levels
            response["market_analysis"]["resistance_levels"] = resistance_levels
            response["market_analysis"]["volume_profile"] = volume_profile
            response["market_analysis"]["time_of_day_factor"] = time_of_day_factor
            response["market_analysis"]["intraday_volatility"] = intraday_volatility
            response["market_analysis"]["relative_volume"] = relative_volume

            # For intraday, use more sensitive and adaptive thresholds
            PROFIT_THRESHOLD_SMALL = helpers.calculate_dynamic_profit_threshold(recent_prices, symbol, multiplier=0.6)[0]
            PROFIT_THRESHOLD_MEDIUM = helpers.calculate_dynamic_profit_threshold(recent_prices, symbol, multiplier=0.8)[1]
            PROFIT_THRESHOLD_LARGE = helpers.calculate_dynamic_profit_threshold(recent_prices, symbol, multiplier=0.9)[2]

            # Make thresholds time-of-day aware - adjust based on historical volatility patterns at this time
            if time_of_day_factor > 1.2:  # High activity time periods
                PROFIT_THRESHOLD_SMALL *= 1.2
                PROFIT_THRESHOLD_MEDIUM *= 1.1
                PROFIT_THRESHOLD_LARGE *= 1.05
            elif time_of_day_factor < 0.8:  # Low activity time periods
                PROFIT_THRESHOLD_SMALL *= 0.8
                PROFIT_THRESHOLD_MEDIUM *= 0.9
                PROFIT_THRESHOLD_LARGE *= 0.95

            # For intraday, we care about shorter trends
            CONSECUTIVE_PRICE_INCREASES_THRESHOLD = max(2, helpers.dynamic_consecutive_increase_threshold(price_changes, symbol) - 1)
            PRICE_VOLATILITY_THRESHOLD = helpers.calculate_volatility_threshold(recent_prices, symbol) * 0.8  # More sensitive

            # Add the dynamic thresholds to the response
            response["metrics"]["profit_threshold_small"] = PROFIT_THRESHOLD_SMALL
            response["metrics"]["profit_threshold_medium"] = PROFIT_THRESHOLD_MEDIUM
            response["metrics"]["profit_threshold_large"] = PROFIT_THRESHOLD_LARGE
            response["metrics"]["consecutive_threshold"] = CONSECUTIVE_PRICE_INCREASES_THRESHOLD
            response["metrics"]["volatility_threshold"] = PRICE_VOLATILITY_THRESHOLD

            price_direction = "up" if sum(price_changes) > 0 else "down"
            short_term_price_direction = "up" if sum(short_term_changes) > 0 else "down"

            # Update response with trend information
            response["metrics"]["trend_direction"] = price_direction
            response["metrics"]["recent_prices"] = recent_prices[:5]  # Just show the 5 most recent ones

            if open_positions.status == "OPEN":
                # Only create trades if we have sufficient quantity
                if not zero_quantity_mode:
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
                else:
                    # In zero quantity mode, skip trade creation and go directly to monitoring for swaps
                    logger.info(f"Zero quantity mode for {symbol}, skipping trade creation, monitoring for swap opportunities")
                    response["status"] = "ZERO_QUANTITY_MONITORING"

            #get trades from symbol (only if not in zero quantity mode)
            if not zero_quantity_mode:
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
            else:
                # In zero quantity mode, create mock trades for monitoring purposes (not actual trades)
                buy_entry, sell_entry = self.strategy.calculate_entry_levels(current_price)
                buy_trades = []  # Empty list
                sell_trades = []  # Empty list
                trades = []  # Empty list

                # Create mock trade objects for calculations (not saved to DB)
                class MockTrade:
                    def __init__(self, entry_price, side):
                        self.entry_price = entry_price
                        self.side = side

                mock_buy_trade = MockTrade(buy_entry, "BUY")
                mock_sell_trade = MockTrade(sell_entry, "SELL")
                buy_trades = [mock_buy_trade]
                sell_trades = [mock_sell_trade]

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

            # Calculate potential profit percentages with safety checks using log returns
            try:
                # Log returns for more accurate profit percentage calculation
                buy_profit_pct = math.log(current_price / buy_trades[0].entry_price) if buy_trades[0].entry_price > 0 else 0
                sell_profit_pct = math.log(sell_trades[0].entry_price / current_price) if sell_trades[0].entry_price > 0 and current_price > 0 else 0

                # Update profit/loss metrics using log returns
                if current_price > open_positions.average_entry_price:
                    profit_loss = (current_price - open_positions.average_entry_price) * quantity
                    profit_loss_pct = math.log(current_price / open_positions.average_entry_price) * 100
                else:
                    profit_loss = (open_positions.average_entry_price - current_price) * quantity * -1
                    profit_loss_pct = math.log(current_price / open_positions.average_entry_price) * 100

                response["metrics"]["profit_loss"] = profit_loss
                response["metrics"]["profit_loss_percent"] = profit_loss_pct
                response["metrics"]["buy_profit_percent"] = buy_profit_pct * 100
                response["metrics"]["sell_profit_percent"] = sell_profit_pct * 100
            except Exception as e:
                logger.error(f"Error calculating profit percentages: {str(e)}")
                buy_profit_pct = 0
                sell_profit_pct = 0

            # Enhanced decision making for intraday trading
            should_close_buy = False
            should_close_sell = False
            should_swap_to_stable = False
            should_swap_from_stable = False
            swap_percentage = 0.5  # Default swap percentage

            # Dynamic threshold based on multiple factors
            dynamic_threshold = PROFIT_THRESHOLD_SMALL

            # Adjust threshold based on trend strength and volatility
            if consecutive_same_direction >= CONSECUTIVE_PRICE_INCREASES_THRESHOLD:
                dynamic_threshold = PROFIT_THRESHOLD_MEDIUM
            if price_volatility >= PRICE_VOLATILITY_THRESHOLD:
                dynamic_threshold = PROFIT_THRESHOLD_LARGE

            # Further adjust based on intraday pattern recognition
            if intraday_pattern in ["double_top", "head_shoulders"]:
                dynamic_threshold *= 0.9  # Lower threshold to exit earlier on bearish patterns
            elif intraday_pattern in ["double_bottom", "inverse_head_shoulders"]:
                dynamic_threshold *= 1.1  # Higher threshold to stay in bullish patterns

            # Factor in volume profile
            if volume_profile == "distribution":
                dynamic_threshold *= 0.85  # Lower threshold on distribution (selling pressure)
            elif volume_profile == "accumulation":
                dynamic_threshold *= 1.15  # Higher threshold on accumulation (buying pressure)

            # Factor in relative volume
            if relative_volume > 1.5:  # Much higher volume than average
                dynamic_threshold *= 0.9  # More sensitive threshold as high volume suggests stronger moves

            # Factor in proximity to support/resistance levels
            for level in resistance_levels:
                # If we're approaching a resistance level (within 1%)
                if current_price * 1.01 >= level >= current_price:
                    dynamic_threshold *= 0.85  # Lower threshold to take profit sooner
                    break

            for level in support_levels:
                # If we're approaching a support level (within 1%)
                if current_price <= level <= current_price * 1.01:
                    dynamic_threshold *= 0.85  # Lower threshold to close positions sooner
                    break

            # Update response with threshold
            response["metrics"]["profit_threshold"] = dynamic_threshold

            # Profitable BUY condition - if price has increased enough from our buy entry
            if buy_profit_pct >= dynamic_threshold or buy_profit_pct >= 0:
                should_close_buy = True

                # Determine if and how much to swap to stablecoin based on multiple factors
                if price_direction == "up":
                    # Determine swap percentage based on market conditions
                    if intraday_pattern in ["double_top", "head_shoulders"]:
                        # Bearish patterns despite uptrend - swap a larger percentage
                        swap_percentage = 0.7
                        should_swap_to_stable = True
                    elif consecutive_same_direction >= CONSECUTIVE_PRICE_INCREASES_THRESHOLD:
                        # Strong uptrend - swap a moderate amount to secure some profits
                        swap_percentage = 0.4
                        should_swap_to_stable = True
                    elif time_of_day_factor < 0.8:
                        # Low activity period - safer to secure more profits
                        swap_percentage = 0.6
                        should_swap_to_stable = True
                    else:
                        # Default in uptrend - swap a smaller percentage
                        swap_percentage = 0.3
                        should_swap_to_stable = True
                else:  # downtrend
                    # In a downtrend, consider larger swaps to stablecoin
                    swap_percentage = 0.8
                    should_swap_to_stable = True

                    # If we're seeing high volatility and downtrend
                    if price_volatility >= PRICE_VOLATILITY_THRESHOLD:
                        swap_percentage = 0.9  # Even higher percentage

                    # If volume is higher than average in a downtrend
                    if relative_volume > 1.3:
                        swap_percentage = 1.0  # Swap everything

            # Profitable SELL condition - if price has decreased enough from our sell entry
            if sell_profit_pct >= dynamic_threshold or sell_profit_pct >= 0:
                should_close_sell = True

                # Determine if and how much to swap to stablecoin based on multiple factors
                if price_direction == "down":
                    # Determine swap percentage based on market conditions
                    if intraday_pattern in ["double_bottom", "inverse_head_shoulders"]:
                        # Bullish patterns despite downtrend - swap a smaller percentage
                        swap_percentage = 0.5
                    elif consecutive_same_direction >= CONSECUTIVE_PRICE_INCREASES_THRESHOLD:
                        # Strong downtrend - swap a larger percentage
                        swap_percentage = 0.8
                    elif volume_profile == "distribution":
                        # High selling pressure - swap more to stablecoin
                        swap_percentage = 0.9
                    else:
                        # Default in downtrend - swap a moderate amount
                        swap_percentage = 0.7

                    should_swap_to_stable = True
                else:  # uptrend
                    # In an uptrend after profit from selling, still consider some stablecoin
                    swap_percentage = 0.4
                    should_swap_to_stable = True

            # Enhanced swap-back logic for buying back into crypto
            # If price rebounds after a downtrend, consider buying back
            if price_direction == "up" and consecutive_same_direction >= 2:
                # Check for bullish intraday patterns
                if intraday_pattern in ["double_bottom", "inverse_head_shoulders"]:
                    should_swap_from_stable = True
                # Check if we're bouncing off a support level
                elif any(abs(current_price - support) / support < 0.02 for support in support_levels):
                    should_swap_from_stable = True
                # Check volume profile
                elif volume_profile == "accumulation" and relative_volume > 1.2:
                    should_swap_from_stable = True
                # Time of day effect - if historically good time to buy
                elif time_of_day_factor > 1.3:
                    should_swap_from_stable = True

            # Execute the determined strategy
            if (should_close_buy or should_close_sell) and current_price > buy_trades[0].entry_price:
                logger.info(f"Closing positions for {symbol} due to price increase to {current_price} from {buy_trades[0].entry_price}")
                # close old trades
                closed_trades = await self.close_straddle_trades(symbol)
                # create new straddle trades
                new_trades = await self.create_straddle_trades(symbol, current_price, quantity, position_id)

                # If we should swap to stablecoin
                swap_performed = False
                should_swap_to_stable = False
                if should_swap_to_stable:
                    logger.info(f"Swapping {symbol} to stablecoin due to price increase, profit: {buy_profit_pct*100:.2f}%")
                    swap_percentage = 1
                    # Calculate amount to swap based on determined percentage
                    swap_amount = quantity * swap_percentage
                    if swap_amount > 0:
                        # Get the best stablecoin to swap to
                        stable_coin_data = await binance_helper.get_best_stable_coin()
                        target_stable = stable_coin_data["best_stable"]

                        swap_result = await swap_service.swap_symbol_stable_coin(
                            symbol,
                            swap_amount,
                            current_price,
                            target_stablecoin=target_stable,
                            position_id=position_id
                        )
                        swap_performed = True

                        # Update swap status
                        response["swap_status"]["swap_transaction_id"] = swap_result["transaction"]["transaction_id"]
                        response["swap_status"]["performed"] = True
                        response["swap_status"]["from_coin"] = symbol
                        response["swap_status"]["to_coin"] = target_stable
                        response["swap_status"]["amount"] = swap_amount
                        response["swap_status"]["price"] = current_price
                        response["swap_status"]["percentage"] = swap_percentage * 100
                        response["swap_status"]["reason"] = "Price increased with uptrend"

                # Update response
                # Refresh each trade individually
                for trade in new_trades:
                    await self.db.refresh(trade)
                response["status"] = "PROFIT_TAKEN"
                if swap_performed:
                    response["reason"] = f"Price increased to {current_price} and performed swap ({swap_percentage*100:.0f}%)"
                else:
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
                # If price is declining, consider swapping to stablecoin
                if should_swap_to_stable:
                    logger.info(f"Swapping {symbol} to stablecoin due to downtrend, profit: {sell_profit_pct*100:.2f}%")
                    swap_percentage = 1
                    # Calculate amount to swap based on determined percentage
                    swap_amount = quantity * swap_percentage
                    if swap_amount > 0:
                        # Get the best stablecoin to swap to
                        stable_coin_data = await binance_helper.get_best_stable_coin()
                        target_stable = stable_coin_data["best_stable"]
                        #Done
                        swap_result = await swap_service.swap_symbol_stable_coin(
                            symbol,
                            swap_amount,
                            current_price,
                            target_stablecoin=target_stable,
                            position_id=position_id
                        )
                        swap_performed = True

                        # Update swap status
                        response["swap_status"]["swap_transaction_id"] = swap_result["transaction"]["transaction_id"]
                        response["swap_status"]["performed"] = True
                        response["swap_status"]["from_coin"] = symbol
                        response["swap_status"]["to_coin"] = target_stable
                        response["swap_status"]["amount"] = swap_amount
                        response["swap_status"]["price"] = current_price
                        response["swap_status"]["percentage"] = swap_percentage * 100
                        response["swap_status"]["reason"] = "Price decreased with downtrend"


                # Update response
                # Refresh each trade individually
                for trade in new_trades:
                    await self.db.refresh(trade)
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

            if (current_price < buy_trades[0].entry_price and current_price > sell_trades[0].entry_price):
                logger.info(f"Price {current_price} is in monitoring range for {symbol} (between {sell_trades[0].entry_price} and {buy_trades[0].entry_price})")

                # Enhanced monitoring logic - works for both normal and zero quantity modes
                # This runs during the monitoring phase and checks if we should swap back from stablecoin
                is_buy = self.strategy.is_good_buy_entry(price_direction, short_term_changes, relative_volume, current_price, support_levels, resistance_levels)
                if short_term_price_direction == "up" and (price_direction == "up" or consecutive_same_direction >= 2) and \
                    self.strategy.is_good_buy_entry(
                        price_direction,
                        short_term_changes,
                        relative_volume,
                        current_price,
                        support_levels,
                        resistance_levels
                    ):
                    # Get available stablecoins regardless of main symbol quantity
                    stable_coin_data = await binance_helper.get_best_stable_coin()
                    available_stables = stable_coin_data["available_stables"]

                    # Find the best stablecoin to swap from based on available quantity
                    best_stable_to_swap_from = None
                    largest_amount = 0

                    for stable in available_stables:
                        # Check if we have this stablecoin in portfolio
                        stable_portfolio = await portfolio_crud.get_by_user_and_symbol(self.db, symbol=stable)

                        if stable_portfolio and stable_portfolio.quantity > largest_amount:
                            best_stable_to_swap_from = stable
                            largest_amount = stable_portfolio.quantity

                    if best_stable_to_swap_from and largest_amount > 0:
                        logger.info(f"Found {largest_amount} {best_stable_to_swap_from} available for potential swap to {symbol}")

                        # Determine if we should swap based on technical conditions
                        should_swap_back = False
                        swap_back_percentage = 0.2  # Default - start conservative

                        # In zero quantity mode, be more aggressive about swapping since we have no crypto exposure
                        if zero_quantity_mode:
                            should_swap_back = True  # Always consider swapping when we have zero crypto
                            swap_back_percentage = 0.5  # More aggressive in zero quantity mode
                            logger.info(f"Zero quantity mode active - being more aggressive about swapping to {symbol}")

                        # Check for bullish intraday patterns
                        if intraday_pattern in ["double_bottom", "inverse_head_shoulders"]:
                            should_swap_back = True
                            swap_back_percentage = max(swap_back_percentage, 0.5)  # More bullish pattern

                        # Check if we're bouncing off a support level
                        elif any(abs(current_price - support) / support < 0.02 for support in support_levels):
                            should_swap_back = True
                            swap_back_percentage = max(swap_back_percentage, 0.3)

                        # Check volume profile for accumulation
                        elif volume_profile == "accumulation" and relative_volume > 1.2:
                            should_swap_back = True
                            swap_back_percentage += 0.2  # Strong buying pressure

                        # Time of day effect - if historically good time to buy
                        elif time_of_day_factor > 1.3:
                            should_swap_back = True
                            swap_back_percentage += 0.1

                        # Strong uptrend developing - be more aggressive
                        if consecutive_same_direction >= 3 and price_direction == "up":
                            should_swap_back = True
                            swap_back_percentage += 0.2

                        # Check recent price action for rapid upward movement
                        if len(short_term_prices) >= 5:
                            recent_change = (short_term_prices[-1] - short_term_prices[-5]) / short_term_prices[-5]
                            if recent_change > 0.02:  # 2% increase in recent candles
                                should_swap_back = True
                                swap_back_percentage += 0.1

                        # close old trades
                        closed_trades = await self.close_straddle_trades(symbol)
                        # create new straddle trades
                        new_trades = await self.create_straddle_trades(symbol, current_price, quantity, position_id)

                        # Cap the percentage (higher cap in zero quantity mode)
                        max_percentage = 0.9 if zero_quantity_mode else 0.7
                        swap_back_percentage = min(max_percentage, swap_back_percentage)

                        # Execute swap if conditions are met
                        if should_swap_back:
                            # In zero quantity mode, use full percentage to get meaningful crypto exposure
                            if zero_quantity_mode:
                                swap_back_percentage = 0.8  # Use 80% of stablecoin for initial crypto purchase

                            swap_back_percentage = 1
                            crypto_amount = (trade_amount * current_price) / 1
                            swap_amount = min(crypto_amount * swap_back_percentage, largest_amount)
                            if swap_amount > 0 and swap_amount > protfolo_details.max_trade_limit:
                                swap_reason = "Zero quantity mode - initial crypto purchase" if zero_quantity_mode else "Detected trend reversal"
                                logger.info(f"Swapping {swap_back_percentage*100:.1f}% from {best_stable_to_swap_from} to {symbol}: {swap_reason}")

                                swap_result = await swap_service.swap_stable_coin_symbol(
                                    best_stable_to_swap_from,
                                    symbol,
                                    swap_amount,
                                    position_id=position_id
                                )

                                # Update swap status
                                response["swap_status"]["performed"] = True
                                response["swap_status"]["swap_transaction_id"] = swap_result.get("transaction", {}).get("transaction_id")
                                response["swap_status"]["from_coin"] = best_stable_to_swap_from
                                response["swap_status"]["to_coin"] = symbol
                                response["swap_status"]["amount"] = swap_amount
                                response["swap_status"]["price"] = current_price
                                response["swap_status"]["percentage"] = swap_back_percentage * 100
                                response["swap_status"]["reason"] = swap_reason
                                response["status"] = "SWAP_PERFORMED"
                                response["reason"] = f"{swap_reason}: swapped {swap_back_percentage*100:.1f}% from {best_stable_to_swap_from} to {symbol}"
                    else:
                        logger.info(f"No suitable stablecoin found for swap. Available stables: {available_stables}")
                        if zero_quantity_mode:
                            response["suggestions"] = [
                                "No stablecoins available for swapping",
                                "Consider adding USDT, USDC, or BUSD to your portfolio",
                                "Fund your account with stablecoins to enable automatic buying"
                            ]

                # Update response for monitoring state
                if response["status"] not in ["SWAP_PERFORMED"]:
                    if zero_quantity_mode:
                        response["status"] = "ZERO_QUANTITY_MONITORING"
                    else:
                        response["status"] = "MONITORING"

                # Refresh trades only if we have actual trades (not in zero quantity mode)
                if not zero_quantity_mode:
                    for trade in trades:
                        await self.db.refresh(trade)
                    response["trades"] = [self._trade_to_dict(trade) for trade in trades]
                else:
                    response["trades"] = []  # No actual trades in zero quantity mode

            # At the end of the function, before returning and after all operations are complete,
             # New check: Update portfolio with live data regularly
            # Always update portfolio with live data and market metrics during intraday trading
            try:
                # Get comprehensive portfolio update with market metrics
                portfolio_summary = await self.update_portfolio_summary(
                    symbol,
                    update_crypto=True,  # Always update with latest crypto data
                    include_market_metrics=True  # Include detailed market metrics for decision making
                )
                # Add portfolio summary to response
                response["portfolio_summary"] = portfolio_summary
            except Exception as summary_error:
                logger.error(f"Error updating portfolio summary: {str(summary_error)}")

            # Continue with rest of the function...
            # We've already updated the portfolio at the beginning, so don't need to do it again
            await notification_service.send_straddle_status_notification(response)
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

    def get_minimum_trade_quantity(self, symbol: str, current_price: float) -> float:
        """
        Calculate minimum viable quantity for straddle trading
        This considers minimum order size requirements and practical trading limits
        """
        try:
            # Base minimum quantity (could be configured per symbol)
            base_minimum = 0.001  # Very small default minimum

            # For symbols with higher prices, adjust minimum quantity
            if current_price > 50000:  # Like BTC
                return max(base_minimum, 0.0001)
            elif current_price > 1000:  # Like ETH
                return max(base_minimum, 0.001)
            elif current_price > 100:  # Like BNB
                return max(base_minimum, 0.01)
            elif current_price > 1:  # Like ADA, DOT
                return max(base_minimum, 0.1)
            else:  # Very low price coins
                return max(base_minimum, 1.0)

        except Exception as e:
            logger.error(f"Error calculating minimum quantity for {symbol}: {str(e)}")
            return 0.001  # Safe default

    def validate_trade_quantity(self, symbol: str, quantity: float, current_price: float) -> bool:
        """
        Validate if the quantity is sufficient for trading
        """
        try:
            min_quantity = self.get_minimum_trade_quantity(symbol, current_price)
            min_notional_value = 10.0  # Minimum $10 trade value

            # Check minimum quantity
            if quantity < min_quantity:
                logger.warning(f"Quantity {quantity} below minimum {min_quantity} for {symbol}")
                return False

            # Check minimum notional value
            trade_value = quantity * current_price
            if trade_value < min_notional_value:
                logger.warning(f"Trade value ${trade_value:.2f} below minimum ${min_notional_value} for {symbol}")
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating trade quantity for {symbol}: {str(e)}")
            return False

straddle_service = StraddleService(None)  # Will be initialized with DB session later
