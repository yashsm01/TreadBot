from typing import Optional
from datetime import datetime
from app.core.logger import logger
import asyncio

class NotificationService:
    def __init__(self):
        self.telegram_service = None
        self.db = None

    def set_db(self, db):
        """Set the database session"""
        self.db = db

    async def _get_telegram_service(self):
        """Lazy-load the telegram_service to avoid circular imports"""
        if self.telegram_service is None:
            from app.services.telegram_service import TelegramService
            # Get the singleton instance
            self.telegram_service = TelegramService.get_instance()

            # Ensure the DB session is passed
            if self.db and not self.telegram_service.db:
                self.telegram_service.db = self.db

            # Check if the service is initialized, if not try to initialize it
            if not self.telegram_service._initialized:
                logger.warning("Telegram service not initialized, attempting to initialize now")
                try:
                    await self.telegram_service.initialize()
                    if self.telegram_service._initialized:
                        logger.info("Successfully initialized Telegram service")
                except Exception as e:
                    logger.error(f"Failed to initialize Telegram service: {str(e)}")

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
                f"Current Price: ${current_price:.2f}\n"
                f"Buy Stop: ${buy_entry:.2f}\n"
                f"Sell Stop: ${sell_entry:.2f}\n"
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

                # Get swap status
                swap = trading_status.get('swap_status', {})
                swap_performed = swap.get('performed', False)

                # Add appropriate emoji based on status
                status_emoji = "✅" if status in ["INITIATED", "RECREATED"] else "⚠️" if status in ["SKIPPED", "DISABLED"] else "❌" if status == "CLOSED" else "💤" if status == "IDLE" else "❓"

                # Add emoji for trend
                trend_emoji = "📈" if trend_direction == "up" else "📉" if trend_direction == "down" else "↔️"

                # Add emoji for profit/loss
                pnl_emoji = "🟢" if profit_loss > 0 else "🔴" if profit_loss < 0 else "⚪"

                # Format the message with Markdown
                message = (
                    f"{status_emoji} *Straddle Status Update for {symbol}*\n\n"
                    f"*Status:* {status}\n"
                )

                # Add reason if present
                if trading_status.get('reason'):
                    message += f"*Reason:* {trading_status['reason']}\n"

                # Add position metrics if we have a valid position
                if current_price > 0 and status not in ["NO_POSITION"]:
                    # Price and position info
                    message += (
                        f"\n*Position Details:*\n"
                        f"Current Price: ${current_price:,.2f}\n"
                        f"Entry Price: ${starting_price:,.2f}\n"
                        f"Size: {position_size:,.6f}\n"
                        f"PnL: {pnl_emoji} ${profit_loss:,.2f} ({profit_loss_percent:+.2f}%)\n"
                    )

                    # Add trend analysis if available
                    if trend_direction:
                        message += (
                            f"\n*Market Trend:*\n"
                            f"Direction: {trend_emoji} {trend_direction.upper()}\n"
                            f"Strength: {'🔥' if trend_strength >= 3 else '✨' if trend_strength >= 2 else '🌱' if trend_strength >= 1 else '💤'} {trend_strength}/5\n"
                            f"Volatility: {'🌋' if volatility >= 0.03 else '🌊' if volatility >= 0.015 else '🌱'} {volatility:.2%}\n"
                        )

                    # Add swap info if a swap was performed
                    if swap_performed:
                        message += (
                            f"\n*Swap Performed:*\n"
                            f"From: {swap.get('from_coin', '')}\n"
                            f"To: {swap.get('to_coin', '')}\n"
                            f"Amount: {swap.get('amount', 0):,.6f}\n"
                            f"Price: ${swap.get('price', 0):,.2f}\n"
                        )

                # Send the message
                result = await self.send_message(message)
                if result:
                    logger.info(f"Successfully sent straddle status notification for {symbol}")
                    return True
                else:
                    if retries < max_retries - 1:
                        retries += 1
                        logger.warning(f"Failed to send notification (attempt {retries}/{max_retries}), retrying...")
                        await asyncio.sleep(2)  # Wait before retry
                    else:
                        logger.error(f"Failed to send straddle status notification after {max_retries} attempts")
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
