from typing import Optional
from datetime import datetime
from app.core.logger import logger
import asyncio
import re

class NotificationService:
    def __init__(self):
        self.telegram_service = None
        self.db = None

    def set_db(self, db):
        """Set the database session"""
        self.db = db

    def _escape_markdown(self, text):
        """Escape special Markdown characters to prevent parsing errors"""
        if not text:
            return ""
        # Escape special Markdown characters: _ * [ ] ( ) ~ ` > # + - = | { } . !
        return re.sub(r'([_*\[\]()~`>#\+\-=|{}.!])', r'\\\1', str(text))

    async def _get_telegram_service(self):
        """Lazy-load the telegram_service to avoid circular imports"""
        if self.telegram_service is None:
            from app.services.telegram_service import TelegramService
            # Get the singleton instance
            self.telegram_service = TelegramService.get_instance()

            # Ensure the DB session is passed
            if self.db and not self.telegram_service.db:
                self.telegram_service.db = self.db

            # Don't try to initialize here - should be done in main.py startup
            if not self.telegram_service._initialized:
                logger.debug("Telegram service not initialized, notifications will be skipped")
                # Don't try to initialize here to avoid conflicts

        return self.telegram_service

    async def send_message(self, message: str):
        """Send a message via Telegram"""
        try:
            # Lazy-load the telegram service
            telegram_service = await self._get_telegram_service()

            # Send message to telegram if initialized
            if telegram_service._initialized:
                result = await telegram_service.send_message(message)
                if result:
                    logger.info(f"Telegram message sent: {message}")
                    return True
                else:
                    logger.warning(f"Telegram message delivery failed: {message}")
                    return False
            else:
                logger.warning(f"Telegram service not initialized, message not sent: {message}")
                return False
        except Exception as e:
            logger.error(f"Error sending Telegram message: {str(e)}")
            return False

    async def send_trade_notification(self,
                                    symbol: str,
                                    side: str,
                                    entry_price: float,
                                    quantity: float,
                                    trade_type: str = "NEW"):
        """Send trade-related notification"""
        try:
            emoji = "🔄" if trade_type == "NEW" else "📈" if side == "BUY" else "📉"
            message = (
                f"{emoji} {trade_type} Trade for {symbol}\n"
                f"Side: {side}\n"
                f"Price: ${entry_price:.2f}\n"
                f"Size: {quantity}"
            )
            await self.send_message(message)
        except Exception as e:
            logger.error(f"Error sending trade notification: {str(e)}")

    async def send_breakout_notification(self,
                                       symbol: str,
                                       direction: str,
                                       price: float,
                                       confidence: float,
                                       indicators: dict):
        """Send breakout detection notification"""
        try:
            direction_emoji = "📈" if direction == "UP" else "📉"
            message = (
                f"{direction_emoji} Breakout Detected for {symbol}\n"
                f"Direction: {direction}\n"
                f"Price: ${price:.2f}\n"
                f"Confidence: {confidence:.2%}\n"
                f"Indicators:\n"
                f"Volume Spike: {'✅' if indicators.get('volume_spike') else '❌'}\n"
                f"RSI Divergence: {'✅' if indicators.get('rsi_divergence') else '❌'}\n"
                f"MACD Crossover: {'✅' if indicators.get('macd_crossover') else '❌'}"
            )
            await self.send_message(message)
        except Exception as e:
            logger.error(f"Error sending breakout notification: {str(e)}")

    async def send_straddle_setup_notification(self,
                                             symbol: str,
                                             current_price: float,
                                             buy_entry: float,
                                             sell_entry: float,
                                             quantity: float):
        """Send straddle setup notification"""
        try:
            message = (
                f"🔄 New Straddle Setup for {symbol}\n"
                f"Current Price: ${current_price:.5f}\n"
                f"Buy Stop: ${buy_entry:.5f}\n"
                f"Sell Stop: ${sell_entry:.5f}\n"
                f"Position Size: {quantity}"
            )
            await self.send_message(message)
        except Exception as e:
            logger.error(f"Error sending straddle setup notification: {str(e)}")

    async def send_position_close_notification(self,
                                             symbol: str,
                                             side: str,
                                             entry_price: float,
                                             exit_price: float,
                                             pnl: float):
        """Send position closure notification"""
        try:
            message = (
                f"🔒 Closed {side} position for {symbol}\n"
                f"Entry: ${entry_price:.2f}\n"
                f"Exit: ${exit_price:.2f}\n"
                f"PnL: {pnl:.2%}"
            )
            await self.send_message(message)
        except Exception as e:
            logger.error(f"Error sending position close notification: {str(e)}")

    async def send_straddle_status_notification(self,
                                  trading_status: dict,
                                  max_retries: int = 3):
        """Send detailed straddle status notification with enhanced data

        Args:
            trading_status: Comprehensive trading status data from auto_buy_sell_straddle_inprogress
            max_retries: Maximum number of retries for sending the message if Telegram service isn't ready
        """
        retries = 0
        while retries < max_retries:
            try:
                # Check if Telegram service is initialized
                telegram_service = await self._get_telegram_service()
                if not telegram_service._initialized:
                    retries += 1
                    logger.warning(f"Telegram service not initialized (attempt {retries}/{max_retries}), retrying...")
                    await asyncio.sleep(2)  # Wait before retry
                    continue

                # Get symbol and basic status
                symbol = trading_status.get('symbol', 'Unknown')
                status = trading_status.get('status', 'UNKNOWN')

                # Escape Markdown special characters
                symbol_escaped = self._escape_markdown(symbol)
                status_escaped = self._escape_markdown(status)

                # Get metrics
                metrics = trading_status.get('metrics', {})
                current_price = metrics.get('current_price', 0)
                starting_price = metrics.get('starting_price', 0)
                profit_loss = metrics.get('profit_loss', 0)
                profit_loss_percent = metrics.get('profit_loss_percent', 0)
                position_size = metrics.get('position_size', 0)

                # Get trend information
                trend_direction = metrics.get('trend_direction', 'neutral')
                trend_strength = metrics.get('trend_strength', 0)
                volatility = metrics.get('volatility', 0)

                # Get thresholds and percentages
                profit_threshold = metrics.get('profit_threshold', 0)
                profit_threshold_small = metrics.get('profit_threshold_small', 0)
                profit_threshold_medium = metrics.get('profit_threshold_medium', 0)
                profit_threshold_large = metrics.get('profit_threshold_large', 0)

                # Escape trend direction
                trend_direction_escaped = self._escape_markdown(trend_direction)

                # Get swap status
                swap = trading_status.get('swap_status', {})
                swap_performed = swap.get('performed', False)

                # Get portfolio summary if available
                portfolio_summary = trading_status.get('portfolio_summary', {})
                has_portfolio_summary = len(portfolio_summary) > 0

                # Add appropriate emoji based on status
                status_emoji = {
                    "INITIATED": "🚀",
                    "RECREATED": "🔄",
                    "PROFIT_TAKEN": "💰",
                    "SWAP_PERFORMED": "🔄",
                    "MONITORING": "👀",
                    "ZERO_QUANTITY_MONITORING": "⚠️",
                    "SKIPPED": "⏭️",
                    "DISABLED": "🚫",
                    "CLOSED": "🔒",
                    "IDLE": "💤",
                    "ERROR": "❌",
                    "NO_POSITION": "📭",
                    "INSUFFICIENT_QUANTITY": "⚠️"
                }.get(status, "❓")

                # Add emoji for trend
                trend_emoji = "📈" if trend_direction == "up" else "📉" if trend_direction == "down" else "↔️"

                # Add emoji for profit/loss
                pnl_emoji = "🟢" if profit_loss > 0 else "🔴" if profit_loss < 0 else "⚪"

                # Get current timestamp
                current_time = datetime.now().strftime("%H:%M:%S")

                # Format the message with enhanced structure
                message = (
                    f"🤖 {symbol_escaped} *STRADDLE BOT UPDATE* 🤖\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🕐 *Time:* {current_time}\n"
                    f"💎 *Symbol:* {symbol_escaped}\n"
                    f"{status_emoji} *Status:* {status_escaped}\n"
                )

                # Add reason if present
                if trading_status.get('reason'):
                    reason_escaped = self._escape_markdown(trading_status['reason'])
                    message += f"📝 *Reason:* {reason_escaped}\n"

                message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

                # Add portfolio summary info if available
                if has_portfolio_summary and status not in ["ERROR"]:
                    message += (
                        f"💼 *PORTFOLIO OVERVIEW*\n"
                        f"💰 Total Value: ${portfolio_summary.get('total_value', 0):,.2f}\n"
                        f"📊 P/L: {pnl_emoji} ${portfolio_summary.get('total_profit_loss', 0):,.2f} "
                        f"({portfolio_summary.get('total_profit_loss_percentage', 0):+.2f}%)\n"
                    )

                    # Add daily change if available
                    if portfolio_summary.get('daily_change') is not None:
                        daily_emoji = "📈" if portfolio_summary['daily_change'] > 0 else "📉"
                        message += f"📅 Daily Change: {daily_emoji} {portfolio_summary['daily_change']:+.2f}%\n"

                    # Add asset distribution
                    crypto_value = portfolio_summary.get('crypto_value', 0)
                    stable_value = portfolio_summary.get('stable_value', 0)
                    total = crypto_value + stable_value
                    if total > 0:
                        crypto_pct = (crypto_value / total) * 100
                        stable_pct = (stable_value / total) * 100
                        message += f"🔄 Distribution: 🪙 {crypto_pct:.1f}% | 💵 {stable_pct:.1f}%\n"

                    message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

                # Add position metrics if we have a valid position
                if current_price > 0 and status not in ["NO_POSITION"]:
                    # Price and position info
                    message += (
                        f"📍 *POSITION DETAILS*\n"
                        f"📏 Size: {position_size:,.8f} {symbol_escaped}\n"
                        f"🎯 Entry Price: ${starting_price:,.8f}\n"
                        f"💵 Entry Value: ${starting_price * position_size:,.2f}\n"
                        f"💲 Current Price: ${current_price:,.8f}\n"
                        f"💰 Current Value: ${current_price * position_size:,.2f}\n"
                        f"📈 P/L: {pnl_emoji} ${profit_loss:,.2f} ({profit_loss_percent:+.2f}%)\n"
                    )

                    # Add buy/sell trade entry prices if available
                    buy_trades = metrics.get("buy_trades", [])
                    sell_trades = metrics.get("sell_trades", [])

                    if buy_trades and isinstance(buy_trades, list) and len(buy_trades) > 0:
                        buy_trade = buy_trades[0]
                        if "entry_price" in buy_trade:
                            message += f"🟢 Buy Entry: ${buy_trade['entry_price']:.8f}\n"
                            if "take_profit" in buy_trade:
                                message += f"🎯 Buy TP: ${buy_trade['take_profit']:.8f}\n"
                            if "stop_loss" in buy_trade:
                                message += f"🛑 Buy SL: ${buy_trade['stop_loss']:.8f}\n"

                    if sell_trades and isinstance(sell_trades, list) and len(sell_trades) > 0:
                        sell_trade = sell_trades[0]
                        if "entry_price" in sell_trade:
                            message += f"🔴 Sell Entry: ${sell_trade['entry_price']:.8f}\n"
                            if "take_profit" in sell_trade:
                                message += f"🎯 Sell TP: ${sell_trade['take_profit']:.8f}\n"
                            if "stop_loss" in sell_trade:
                                message += f"🛑 Sell SL: ${sell_trade['stop_loss']:.8f}\n"

                    message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

                    # Add trend analysis if available
                    if trend_direction:
                        message += (
                            f"📊 *MARKET ANALYSIS*\n"
                            f"📈 Direction: {trend_emoji} {trend_direction_escaped.upper()}\n"
                            f"💪 Strength: {'🔥' if trend_strength >= 3 else '✨' if trend_strength >= 2 else '🌱' if trend_strength >= 1 else '💤'} {trend_strength}/5\n"
                            f"🌊 Volatility: {'🌋' if volatility >= 0.03 else '🌊' if volatility >= 0.015 else '🌱'} {volatility:.2%}\n"
                        )

                        # Add threshold information
                        if profit_threshold > 0:
                            message += f"🎯 Active Threshold: {profit_threshold:.2%}\n"

                        if profit_threshold_small > 0:
                            message += (
                                f"📏 Thresholds: "
                                f"S:{profit_threshold_small:.2%} | "
                                f"M:{profit_threshold_medium:.2%} | "
                                f"L:{profit_threshold_large:.2%}\n"
                            )

                        message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

                    # Add swap info if a swap was performed
                    if swap_performed:
                        from_coin_escaped = self._escape_markdown(swap.get('from_coin', ''))
                        to_coin_escaped = self._escape_markdown(swap.get('to_coin', ''))
                        swap_reason_escaped = self._escape_markdown(swap.get('reason', ''))
                        message += (
                            f"🔄 *SWAP EXECUTED*\n"
                            f"📤 From: {from_coin_escaped}\n"
                            f"📥 To: {to_coin_escaped}\n"
                            f"💰 Amount: {swap.get('amount', 0):,.6f}\n"
                            f"💲 Price: ${swap.get('price', 0):,.2f}\n"
                            f"📝 Reason: {swap_reason_escaped}\n"
                            f"📊 Percentage: {swap.get('percentage', 0):.1f}%\n"
                        )
                        message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

                # Add suggestions if available
                suggestions = trading_status.get('suggestions', [])
                if suggestions:
                    message += "💡 *SUGGESTIONS*\n"
                    for i, suggestion in enumerate(suggestions[:3], 1):  # Limit to 3 suggestions
                        suggestion_escaped = self._escape_markdown(suggestion)
                        message += f"{i}. {suggestion_escaped}\n"
                    message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

                # Add footer
                message += f"🤖 *Automated Trading System* | Status: {'🟢 Active' if status not in ['DISABLED', 'ERROR'] else '🔴 Inactive'}"

                # Use a fresh database session for sending the message to avoid transaction issues
                try:
                    # Send message with a direct call to avoid reusing potentially bad transactions
                    if telegram_service and telegram_service.application and telegram_service.application.bot:
                        # Get active users directly with a clean transaction
                        from app.crud.crud_telegram import telegram_user
                        from sqlalchemy.ext.asyncio import AsyncSession

                        async with AsyncSession(self.db.bind) as clean_session:
                            active_users = await telegram_user.get_active_users(clean_session)

                            if not active_users:
                                logger.warning(f"No active users to send message to")
                                return False

                            success_count = 0
                            for user in active_users:
                                try:
                                    await telegram_service.application.bot.send_message(
                                        chat_id=user.chat_id,
                                        text=message,
                                        parse_mode='Markdown'
                                    )
                                    success_count += 1
                                except Exception as msg_error:
                                    logger.error(f"Failed to send message to user {user.id}: {str(msg_error)}")

                            if success_count > 0:
                                logger.info(f"Enhanced straddle status notification sent to {success_count}/{len(active_users)} users")
                                return True
                            else:
                                logger.warning(f"Failed to send notification to any users")
                                if retries < max_retries - 1:
                                    retries += 1
                                    await asyncio.sleep(2)  # Wait before retry
                                    continue
                                else:
                                    return False
                    else:
                        # Fallback to regular send_message if direct approach not available
                        result = await telegram_service.send_message(message)
                        if result:
                            logger.info(f"Successfully sent enhanced straddle status notification for {symbol}")
                            return True
                        else:
                            if retries < max_retries - 1:
                                retries += 1
                                logger.warning(f"Failed to send notification (attempt {retries}/{max_retries}), retrying...")
                                await asyncio.sleep(2)  # Wait before retry
                            else:
                                logger.error(f"Failed to send straddle status notification after {max_retries} attempts")
                                return False
                except Exception as tx_error:
                    logger.error(f"Transaction error in notification: {str(tx_error)}")
                    if retries < max_retries - 1:
                        retries += 1
                        logger.warning(f"Transaction error (attempt {retries}/{max_retries}), retrying...")
                        await asyncio.sleep(2)  # Wait before retry
                    else:
                        logger.error(f"Failed to send notification after {max_retries} attempts due to transaction errors")
                        return False
            except Exception as e:
                logger.error(f"Error sending straddle status notification: {str(e)}")
                if retries < max_retries - 1:
                    retries += 1
                    logger.warning(f"Exception during notification (attempt {retries}/{max_retries}), retrying...")
                    await asyncio.sleep(2)  # Wait before retry
                else:
                    logger.error(f"Failed to send straddle status notification after {max_retries} attempts due to exception")
                    return False

        return False

notification_service = NotificationService()
