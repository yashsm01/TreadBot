import logging
from typing import Dict, Optional, List
from datetime import datetime
from telegram import Bot, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.telegram import TelegramUser, TelegramNotification
from app.crud.crud_telegram import telegram_user as user_crud
from app.crud.crud_telegram import telegram_notification as notification_crud


  # Import services here to avoid circular imports
from app.services.market_analyzer import market_analyzer
from app.services.portfolio_service import portfolio_service
from app.services.straddle_service import straddle_service
from app.services.helper.binance_helper import binance_helper
from app.services.swap_service import swap_service

logger = logging.getLogger(__name__)

class TelegramService:
    # Singleton instance
    _instance = None
    # Class-level lock
    _instance_running = False

    @classmethod
    def get_instance(cls, db=None, **kwargs):
        """Get or create the singleton instance"""
        if cls._instance is None:
            logger.info("Creating new TelegramService instance (singleton)")
            cls._instance = cls(db=db, **kwargs)
        elif db is not None and cls._instance.db is None:
            # Update DB if needed
            logger.info("Updating database session in TelegramService singleton")
            cls._instance.db = db
        return cls._instance

    def __init__(
        self,
        db: Optional[AsyncSession] = None,
        market_analyzer=market_analyzer,
        portfolio_service=portfolio_service,
        straddle_service=straddle_service,
        binance_helper=binance_helper
    ):
        """
        Initialize TelegramService with dependencies.

        Args:
            db (AsyncSession): SQLAlchemy async database session
            market_analyzer: Service for market analysis
            portfolio_service: Service for portfolio management
            straddle_service: Service for straddle positions
            binance_helper: Helper for Binance API operations
        """
        # Skip initialization if instance already exists (singleton pattern)
        if TelegramService._instance is not None and self is not TelegramService._instance:
            logger.warning("Attempting to create another TelegramService instance - skipping")
            return

        # Regular initialization for the first/singleton instance
        self.db = db
        self.market_analyzer = market_analyzer
        self.portfolio_service = portfolio_service
        self.straddle_service = straddle_service
        self.binance_helper = binance_helper
        self.application = None
        self._initialized = False
        self._semaphore = None  # Will be initialized in initialize()

    # Helper method to handle DB transactions
    async def _db_commit(self):
        """Safely commit database transaction"""
        try:
            await self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Error committing transaction: {str(e)}")
            await self.db.rollback()
            return False

    # Helper method to handle DB rollbacks
    async def _db_rollback(self):
        """Safely rollback database transaction"""
        try:
            await self.db.rollback()
            return True
        except Exception as e:
            logger.error(f"Error rolling back transaction: {str(e)}")
            return False

    async def initialize(self):
        """Initialize the Telegram bot"""
        # Prevent multiple initializations
        if self._initialized:
            logger.info("Telegram service already initialized")
            return True

        # Check if any instance is already running across the application
        if TelegramService._instance_running:
            logger.warning("Another Telegram service instance is already running")
            return False

        try:
            # Mark that we're starting an instance
            TelegramService._instance_running = True

            # Create semaphore for concurrency control
            import asyncio
            self._semaphore = asyncio.Semaphore(1)

            if not settings.TELEGRAM_BOT_TOKEN:
                logger.warning("No Telegram bot token provided. Telegram functionality will be disabled.")
                self._initialized = False
                TelegramService._instance_running = False
                return False

            logger.info("Initializing Telegram bot...")

            # Clear any existing webhook to ensure polling works
            try:
                import requests
                webhook_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/deleteWebhook"
                webhook_response = requests.post(webhook_url, json={"drop_pending_updates": True}, timeout=10)
                if webhook_response.status_code == 200:
                    logger.info("Cleared any existing Telegram webhook")
                else:
                    logger.warning(f"Failed to clear webhook: {webhook_response.status_code}")
            except Exception as e:
                logger.warning(f"Could not clear webhook: {str(e)}")

            self.application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

            # Add command handlers
            self.application.add_handler(CommandHandler("start", self._handle_start))
            self.application.add_handler(CommandHandler("stop", self._handle_stop))
            self.application.add_handler(CommandHandler("update", self._handle_update_command))
            self.application.add_handler(CommandHandler("status", self._handle_status))
            self.application.add_handler(CommandHandler("pairs", self.get_pairs))
            self.application.add_handler(CommandHandler("analysis", self.get_analysis))
            self.application.add_handler(CommandHandler("signals", self.get_signals))
            self.application.add_handler(CommandHandler("help", self.help))

            # Portfolio commands
            self.application.add_handler(CommandHandler("buy", self.handle_buy))
            self.application.add_handler(CommandHandler("sell", self.handle_sell))
            self.application.add_handler(CommandHandler("portfolio", self.get_portfolio))
            self.application.add_handler(CommandHandler("history", self.get_history))
            self.application.add_handler(CommandHandler("profit", self.get_profit))

            # Straddle Strategy commands
            self.application.add_handler(CommandHandler("straddle", self.handle_straddle))
            self.application.add_handler(CommandHandler("update_straddle", self.handle_update_straddle))
            self.application.add_handler(CommandHandler("close_straddle", self.handle_close_straddle))
            self.application.add_handler(CommandHandler("straddles", self.get_straddle_positions))

            # Swap transaction commands
            self.application.add_handler(CommandHandler("swap_crypto", self.handle_swap_crypto_to_stable))
            self.application.add_handler(CommandHandler("swap_stable", self.handle_swap_stable_to_crypto))
            self.application.add_handler(CommandHandler("swap_history", self.get_swap_history))

            # Testing commands
            self.application.add_handler(CommandHandler("price", self.get_price))
            self.application.add_handler(CommandHandler("prices", self.get_multiple_prices))
            self.application.add_handler(CommandHandler("24hstats", self.get_24h_stats))
            self.application.add_handler(CommandHandler("5mstats", self.get_5m_stats))
            self.application.add_handler(CommandHandler("5mpricehistory", self.get_5m_price_history))

            # Add fallback handler for unknown commands
            self.application.add_handler(MessageHandler(filters.COMMAND, self._handle_unknown_command))

            logger.info("Initializing Telegram application...")
            await self.application.initialize()
            await self.application.start()

            # Start polling for updates with error handling
            logger.info("Starting Telegram polling...")
            try:
                await self.application.updater.start_polling(
                    drop_pending_updates=True,  # Drop any pending updates to avoid conflicts
                    poll_interval=1.0,  # Poll every second
                    timeout=10  # 10 second timeout for long polling
                )
            except Exception as polling_error:
                if "Conflict" in str(polling_error):
                    logger.error("Telegram polling conflict detected. Another bot instance may be running.")
                    logger.error("Please stop all other instances and restart the application.")
                raise polling_error

            self._initialized = True
            logger.info("Telegram bot initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Telegram bot: {str(e)}")
            self._initialized = False
            # Release the instance_running lock
            TelegramService._instance_running = False

            # Provide specific guidance for common errors
            if "Conflict" in str(e):
                logger.error("TELEGRAM CONFLICT ERROR:")
                logger.error("This usually means another instance of the bot is already running.")
                logger.error("Solutions:")
                logger.error("1. Stop all other instances of your application")
                logger.error("2. Run: python backend/fix_telegram_conflict.py")
                logger.error("3. Restart your application")

            # Don't raise the exception, just continue without Telegram functionality
            return False

    async def stop(self):
        """Stop the Telegram bot"""
        if self.application:
            if self.application.updater:
                await self.application.updater.stop()
            await self.application.stop()
            logger.info("Telegram bot stopped")
            self._initialized = False
            # Release the instance running lock
            TelegramService._instance_running = False

    async def send_message(self, message: str):
        """
        Send a message to all active users.

        Args:
            message (str): The message to send (supports Markdown formatting)
        """
        if not self._initialized:
            logger.warning("Telegram service not initialized, cannot send message")
            return False

        try:
            # Get all active users from the database
            users = await user_crud.get_active_users(self.db)
            if not users or len(users) == 0:
                logger.warning("No active users to send message to")
                return False

            success_count = 0
            # Send message to each active user
            for user in users:
                try:
                    await self.application.bot.send_message(
                        chat_id=user.chat_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to send message to user {user.id}: {str(e)}")

            logger.info(f"Message sent to {success_count}/{len(users)} active users")
            return success_count > 0
        except Exception as e:
            logger.error(f"Error broadcasting message: {str(e)}")
            return False

    async def send_notification(
        self,
        user_id: int,
        message_type: str,
        content: str,
        symbol: Optional[str] = None
    ):
        """Send notification to user"""
        notification = None
        try:
            # Create notification record
            notification = TelegramNotification(
                user_id=user_id,
                message_type=message_type,
                symbol=symbol,
                content=content
            )
            # Use transaction to ensure atomicity
            self.db.add(notification)
            try:
                await self.db.flush()  # Flush to get the ID but don't commit yet
            except Exception as e:
                logger.error(f"Error flushing database: {str(e)}")
                try:
                    await self.db.rollback()
                except:
                    pass  # Ignore rollback errors
                return False

            # Get user and check if active
            try:
                user = await user_crud.get_by_telegram_id(self.db, telegram_id=user_id)
                if user and user.is_active:
                    # Send message via Telegram
                    await self.application.bot.send_message(
                        chat_id=user.chat_id,
                        text=content,
                        parse_mode='Markdown'
                    )
                    notification.is_sent = True
            except Exception as e:
                logger.error(f"Error getting user or sending message: {str(e)}")
                # Continue to save the notification even if message sending fails

            # Commit the transaction
            try:
                await self.db.commit()
                return True
            except Exception as e:
                logger.error(f"Error committing notification: {str(e)}")
                try:
                    await self.db.rollback()
                except:
                    pass  # Ignore rollback errors
                return False

        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            # Handle the exception by updating the notification with error message
            if notification and hasattr(notification, 'id'):
                notification.error_message = str(e)
                try:
                    await self.db.commit()
                except:
                    try:
                        await self.db.rollback()
                    except:
                        pass  # Ignore rollback errors
            else:
                try:
                    await self.db.rollback()
                except:
                    pass  # Ignore rollback errors
            return False

    # Command Handlers
    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            # Check if user already exists
            existing_user = await user_crud.get_by_telegram_id(db=self.db, telegram_id=update.effective_user.id)

            if existing_user:
                # Update existing user
                existing_user.is_active = True
                existing_user.last_interaction = datetime.utcnow()
                self.db.add(existing_user)
                try:
                    await self.db.commit()
                except Exception as e:
                    logger.error(f"Error committing database changes: {str(e)}")
                    try:
                        await self.db.rollback()
                    except:
                        pass  # Ignore rollback errors

                welcome_msg = (
                    "🤖 Welcome back to the Crypto Trading Bot!\n\n"
                    "Use /help to see available commands.\n"
                    "Your notifications are now active."
                )
            else:
                # Create new user
                user = TelegramUser(
                    telegram_id=update.effective_user.id,
                    chat_id=str(update.effective_chat.id),
                    username=update.effective_user.username
                )
                self.db.add(user)
                try:
                    await self.db.commit()
                except Exception as e:
                    logger.error(f"Error committing database changes: {str(e)}")
                    try:
                        await self.db.rollback()
                    except:
                        pass  # Ignore rollback errors

                welcome_msg = (
                    "🤖 Welcome to the Crypto Trading Bot!\n\n"
                    "Use /help to see available commands.\n"
                    "Your notifications are now active."
                )

            await update.message.reply_text(welcome_msg)
        except Exception as e:
            logger.error(f"Error handling start command: {str(e)}")
            # Safely handle rollback
            if self.db is not None:
                try:
                    await self.db.rollback()
                except:
                    pass  # Ignore rollback errors
            await update.message.reply_text("❌ Failed to start bot. Please try again.")

    async def _handle_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command"""
        try:
            user = await user_crud.get_by_telegram_id(db=self.db, telegram_id=update.effective_user.id)
            if user:
                user.is_active = False
                self.db.add(user)
                await self.db.commit()
                await update.message.reply_text("🔕 Notifications stopped. Use /start to reactivate.")
            else:
                await update.message.reply_text("❌ You need to start the bot first with /start")
        except Exception as e:
            logger.error(f"Error handling stop command: {str(e)}")
            await self.db.rollback()
            await update.message.reply_text("❌ Failed to stop notifications.")

    async def _handle_update_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /update command"""
        try:
            user = await user_crud.get_by_telegram_id(db=self.db, telegram_id=update.effective_user.id)
            if user:
                user.last_interaction = datetime.utcnow()
                self.db.add(user)
                await self.db.commit()
                await update.message.reply_text("✅ User information updated successfully.")
            else:
                await update.message.reply_text("❌ You need to start the bot first with /start")
        except Exception as e:
            logger.error(f"Error handling update command: {str(e)}")
            await self.db.rollback()
            await update.message.reply_text("❌ Failed to update user information.")

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        try:
            user = await user_crud.get_by_telegram_id(db=self.db, telegram_id=update.effective_user.id)
            if user:
                status_msg = (
                    f"📊 Bot Status\n\n"
                    f"User ID: {user.telegram_id}\n"
                    f"Username: {user.username}\n"
                    f"Notifications: {'Active' if user.is_active else 'Inactive'}\n"
                    f"Last Interaction: {user.last_interaction}\n"
                    f"Trading Mode: {'Paper' if settings.PAPER_TRADING else 'Live'}"
                )
                await update.message.reply_text(status_msg)
        except Exception as e:
            logger.error(f"Error handling status command: {str(e)}")
            await update.message.reply_text("❌ Failed to get status.")

    async def get_pairs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pairs command"""
        try:
            pairs = await self.market_analyzer.get_trading_pairs()
            pairs_msg = "📊 Available Trading Pairs:\n\n" + "\n".join(pairs)
            await update.message.reply_text(pairs_msg)
        except Exception as e:
            logger.error(f"Error handling pairs command: {str(e)}")
            await update.message.reply_text("❌ Failed to get trading pairs.")

    async def get_analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /analysis command"""
        try:
            if not context.args or len(context.args) != 1:
                await update.message.reply_text("❌ Please provide a trading pair. Example: /analysis BTC/USDT")
                return

            symbol = context.args[0].upper()
            analysis = await self.market_analyzer.get_market_analysis(symbol)

            analysis_msg = (
                f"📊 Market Analysis for {symbol}\n\n"
                f"Price: ${analysis['current_price']:,.2f}\n"
                # f"24h Change: {analysis['price_change_24h']:,.2f}%\n"
                f"Volume: ${analysis['volume_24h']:,.2f}\n"
                f"Volatility: {analysis['volatility']:,.2f}%\n"
                # f"RSI: {analysis['rsi']:,.2f}\n"
                # f"Trend: {analysis['trend']}\n"
                # f"Signal: {analysis['signal']}"
            )
            await update.message.reply_text(analysis_msg)
        except Exception as e:
            logger.error(f"Error handling analysis command: {str(e)}")
            await update.message.reply_text("❌ Failed to get market analysis.")

    async def get_signals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /signals command"""
        try:
            if not context.args or len(context.args) != 1:
                await update.message.reply_text("❌ Please provide a trading pair. Example: /signals BTC/USDT")
                return

            symbol = context.args[0].upper()
            signals = await self.market_analyzer.get_trading_signal(symbol)

            signals_msg = (
                f"🎯 Trading Signals for {symbol}\n\n"
                f"Primary Signal: {signals['primary_signal']}\n"
                f"Confidence: {signals['confidence']:,.2f}%\n"
                f"Support: ${signals['support']:,.2f}\n"
                f"Resistance: ${signals['resistance']:,.2f}\n"
                f"Stop Loss: ${signals['stop_loss']:,.2f}\n"
                f"Take Profit: ${signals['take_profit']:,.2f}"
            )
            await update.message.reply_text(signals_msg)
        except Exception as e:
            logger.error(f"Error handling signals command: {str(e)}")
            await update.message.reply_text("❌ Failed to get trading signals.")

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_msg = """
🤖 Available Commands:

Basic Commands:
/start - Start the bot
/stop - Stop notifications
/update - Update user information
/status - Check bot status
/help - Show this help message

Market Information:
/pairs - List available trading pairs
/analysis SYMBOL - Get market analysis
/signals SYMBOL - Get trading signals

Portfolio Management:
/buy SYMBOL QUANTITY [PRICE] - Place buy order
/sell SYMBOL QUANTITY [PRICE] - Place sell order
/portfolio - View your portfolio
/history - View trade history
/profit - View profit/loss

Straddle Strategy:
/straddle SYMBOL AMOUNT - Create straddle position
/update_straddle ID PARAMS - Update straddle
/close_straddle ID - Close straddle position
/straddles - View straddle positions

Swap Commands:
/swap_crypto SYMBOL AMOUNT - Swap crypto to stablecoin
/swap_stable STABLE CRYPTO AMOUNT - Swap stablecoin to crypto
/swap_history [LIMIT] - View swap history

Testing Commands:
/price SYMBOL - Get price of a symbol
/prices SYMBOL1 SYMBOL2 SYMBOL3 - Get prices of multiple symbols
/24hstats SYMBOL - Get 24h stats of a symbol
/5mstats SYMBOL - Get 5m stats of a symbol
/5mpricehistory SYMBOL - Get 5m price history of a symbol
Example usage:
/analysis BTC/USDT
/buy BTC/USDT 0.1 50000
/sell BTC/USDT 0.1
/straddle ETHUSDT 1
/swap_crypto BTC 0.01
/swap_stable USDT BTC 100
"""
        await update.message.reply_text(help_msg)

    async def handle_buy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /buy command"""
        try:
            if len(context.args) not in [2, 3]:
                await update.message.reply_text("❌ Usage: /buy SYMBOL QUANTITY [PRICE]\nExample: /buy BTC/USDT 0.1 50000")
                return

            # Get user from database
            user = await user_crud.get_by_telegram_id(self.db, telegram_id=update.effective_user.id)
            if not user:
                await update.message.reply_text("❌ Please start the bot first with /start")
                return

            symbol = context.args[0].upper()
            quantity = float(context.args[1])

            # Get current market price if price not provided
            if len(context.args) == 3:
                price = float(context.args[2])
            else:
                market_data = await self.binance_helper.get_price(symbol)
                price = market_data['price']

            # Check trade viability
            viability = await self.market_analyzer.check_trade_viability(
                symbol=symbol,
                quantity=quantity,
                side="BUY",
                price=price
            )

            if not viability['is_viable']:
                reasons = "\n".join(viability['reasons'])
                await update.message.reply_text(f"❌ Trade not viable:\n{reasons}")
                return

            # Execute buy order
            order = await self.portfolio_service.execute_trade(
                self.db,
                symbol=symbol,
                quantity=quantity,
                side="BUY",
                price=price,
                user_id=user.id
            )

            order_msg = (
                f"✅ Buy Order Executed\n\n"
                f"Symbol: {symbol}\n"
                f"Quantity: {quantity}\n"
                f"Price: ${price:,.2f}\n"
                f"Total: ${order['total']:,.2f}"
            )
            await update.message.reply_text(order_msg)
        except ValueError as e:
            logger.error(f"Error handling buy command: Invalid number format - {str(e)}")
            await update.message.reply_text("❌ Invalid number format. Please check quantity and price values.")
        except Exception as e:
            logger.error(f"Error handling buy command: {str(e)}")
            await update.message.reply_text("❌ Failed to execute buy order.")

    async def handle_sell(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /sell command"""
        try:
            if len(context.args) not in [2, 3]:
                await update.message.reply_text("❌ Usage: /sell SYMBOL QUANTITY [PRICE]\nExample: /sell BTC/USDT 0.1 50000")
                return

            # Get user from database
            user = await user_crud.get_by_telegram_id(self.db, telegram_id=update.effective_user.id)
            if not user:
                await update.message.reply_text("❌ Please start the bot first with /start")
                return

            symbol = context.args[0].upper()
            quantity = float(context.args[1])

            # Get current market price if price not provided
            if len(context.args) == 3:
                price = float(context.args[2])
            else:
                market_data = await self.binance_helper.get_price(symbol)
                price = market_data['price']

            # Check trade viability
            viability = await self.market_analyzer.check_trade_viability(
                symbol=symbol,
                quantity=quantity,
                side="SELL",
                price=price
            )

            if not viability['is_viable']:
                reasons = "\n".join(viability['reasons'])
                await update.message.reply_text(f"❌ Trade not viable:\n{reasons}")
                return

            # Execute sell order
            order = await self.portfolio_service.execute_trade(
                self.db,
                symbol=symbol,
                quantity=quantity,
                side="SELL",
                price=price,
                user_id=user.id
            )

            order_msg = (
                f"✅ Sell Order Executed\n\n"
                f"Symbol: {symbol}\n"
                f"Quantity: {quantity}\n"
                f"Price: ${price:,.2f}\n"
                f"Total: ${order['total']:,.2f}"
            )
            await update.message.reply_text(order_msg)
        except ValueError as e:
            logger.error(f"Error handling sell command: Invalid number format - {str(e)}")
            await update.message.reply_text("❌ Invalid number format. Please check quantity and price values.")
        except Exception as e:
            logger.error(f"Error handling sell command: {str(e)}")
            await update.message.reply_text("❌ Failed to execute sell order.")

    async def get_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /portfolio command"""
        try:
            portfolio = await self.portfolio_service.get_portfolio_summary(self.db)

            if not portfolio['positions']:
                await update.message.reply_text("📊 Your portfolio is empty.")
                return

            portfolio_msg = "📊 Your Portfolio:\n\n"
            for position in portfolio['positions']:
                portfolio_msg += (
                    f"*{position['symbol']}*\n"
                    f"Quantity: {position['quantity']:,.8f}\n"
                    f"Avg Entry: ${position['avg_entry']:,.2f}\n"
                    f"Current Price: ${position['current_price']:,.2f}\n"
                    f"P/L: ${position['unrealized_pnl']:,.2f} ({position['pnl_percentage']:,.2f}%)\n\n"
                )

            portfolio_msg += (
                f"*Summary:*\n"
                f"Total Value: ${portfolio['total_value']:,.2f}\n"
                f"Total P/L: ${portfolio['total_pnl']:,.2f}\n"
                f"24h Change: {portfolio['change_24h']:,.2f}%"
            )

            await update.message.reply_text(portfolio_msg, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error handling portfolio command: {str(e)}")
            await update.message.reply_text("❌ Failed to get portfolio information.")

    async def get_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /history command"""
        try:
            history = await self.portfolio_service.get_trading_performance(self.db)

            history_msg = (
                f"📈 Trading History (Last 30 days)\n\n"
                f"Total Trades: {history['total_trades']}\n"
                f"Winning Trades: {history['winning_trades']}\n"
                f"Losing Trades: {history['losing_trades']}\n"
                f"Win Rate: {history['win_rate']:,.2f}%\n"
                f"Profit Factor: {history['profit_factor']:,.2f}\n"
                f"Total Profit: ${history['total_profit']:,.2f}\n"
                f"Total Loss: ${history['total_loss']:,.2f}"
            )

            await update.message.reply_text(history_msg)
        except Exception as e:
            logger.error(f"Error handling history command: {str(e)}")
            await update.message.reply_text("❌ Failed to get trading history.")

    async def get_profit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /profit command"""
        try:
            profit = await self.portfolio_service.get_portfolio_summary(self.db)

            profit_msg = (
                f"💰 Profit/Loss Summary\n\n"
                f"Realized P/L: ${profit['total_realized_pnl']:,.2f}\n"
                f"Unrealized P/L: ${profit['total_unrealized_pnl']:,.2f}\n"
                f"Total P/L: ${profit['total_pnl']:,.2f}\n"
                f"Active Positions: {profit['active_positions']}\n"
                f"Closed Positions: {profit['closed_positions']}"
            )

            await update.message.reply_text(profit_msg)
        except Exception as e:
            logger.error(f"Error handling profit command: {str(e)}")
            await update.message.reply_text("❌ Failed to get profit information.")

    async def handle_straddle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /straddle command"""
        try:
            if len(context.args) != 2:
                await update.message.reply_text("❌ Usage: /straddle SYMBOL AMOUNT")
                return

            symbol = context.args[0].upper()
            amount = float(context.args[1])

            straddle = await self.straddle_service.create_straddle(
                self.db,
                symbol=symbol,
                amount=amount
            )

            straddle_msg = (
                f"✅ Straddle Position Created\n\n"
                f"ID: {straddle['id']}\n"
                f"Symbol: {straddle['symbol']}\n"
                f"Amount: {straddle['amount']}\n"
                f"Entry Price: ${straddle['entry_price']:,.2f}\n"
                f"Upper Strike: ${straddle['upper_strike']:,.2f}\n"
                f"Lower Strike: ${straddle['lower_strike']:,.2f}"
            )

            await update.message.reply_text(straddle_msg)
        except Exception as e:
            logger.error(f"Error handling straddle command: {str(e)}")
            await update.message.reply_text("❌ Failed to create straddle position.")

    async def handle_update_straddle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /update_straddle command"""
        try:
            if len(context.args) < 2:
                await update.message.reply_text("❌ Usage: /update_straddle ID PARAMS")
                return

            straddle_id = int(context.args[0])
            params = " ".join(context.args[1:])

            updated = await self.straddle_service.update_straddle(
                self.db,
                straddle_id=straddle_id,
                params=params
            )

            update_msg = (
                f"✅ Straddle Position Updated\n\n"
                f"ID: {updated['id']}\n"
                f"New Parameters: {updated['params']}\n"
                f"Current P/L: ${updated['pnl']:,.2f}"
            )

            await update.message.reply_text(update_msg)
        except Exception as e:
            logger.error(f"Error handling update_straddle command: {str(e)}")
            await update.message.reply_text("❌ Failed to update straddle position.")

    async def handle_close_straddle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /close_straddle command"""
        try:
            if len(context.args) != 1:
                await update.message.reply_text("❌ Usage: /close_straddle ID")
                return

            straddle_id = int(context.args[0])

            result = await self.straddle_service.close_straddle(
                self.db,
                straddle_id=straddle_id
            )

            close_msg = (
                f"✅ Straddle Position Closed\n\n"
                f"ID: {result['id']}\n"
                f"Symbol: {result['symbol']}\n"
                f"Final P/L: ${result['final_pnl']:,.2f}\n"
                f"ROI: {result['roi']:,.2f}%"
            )

            await update.message.reply_text(close_msg)
        except Exception as e:
            logger.error(f"Error handling close_straddle command: {str(e)}")
            await update.message.reply_text("❌ Failed to close straddle position.")

    async def get_straddle_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /straddles command"""
        try:
            positions = await self.straddle_service.get_straddle_positions(self.db)

            if not positions:
                await update.message.reply_text("📊 No active straddle positions.")
                return

            positions_msg = "📊 Active Straddle Positions:\n\n"
            for pos in positions:
                positions_msg += (
                    f"*ID: {pos['id']}*\n"
                    f"Symbol: {pos['symbol']}\n"
                    f"Amount: {pos['amount']:,.8f}\n"
                    f"Entry: ${pos['entry_price']:,.2f}\n"
                    f"Current: ${pos['current_price']:,.2f}\n"
                    f"P/L: ${pos['pnl']:,.2f} ({pos['roi']:,.2f}%)\n\n"
                )

            await update.message.reply_text(positions_msg, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error handling straddles command: {str(e)}")
            await update.message.reply_text("❌ Failed to get straddle positions.")

    async def _handle_unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle unknown commands"""
        await update.message.reply_text(
            "❌ Unknown command. Use /help to see available commands."
        )

    async def get_price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /prices command to get prices
        Usage: /prices BTC/USDT
        """
        try:
            symbol = context.args[0].upper()
            price = await self.binance_helper.get_price(symbol)
            await update.message.reply_text(f"Current price of {symbol}: ${price['price']}")
        except Exception as e:
            logger.error(f"Error handling price command: {str(e)}")
            await update.message.reply_text("❌ Failed to get price information.")

    async def get_multiple_prices(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /prices command to get multiple prices
        Usage: /prices BTC/USDT ETH/USDT SOL/USDT
        """
        try:
            symbols = context.args
            prices = await self.binance_helper.get_multiple_prices(symbols)
            for symbol, price_data in prices.items():
                await update.message.reply_text(f"{symbol}: ${price_data['price']} (Updated {datetime.fromtimestamp(price_data['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')})")
        except Exception as e:
            logger.error(f"Error handling prices command: {str(e)}")
            await update.message.reply_text("❌ Failed to get prices information.")

    async def get_24h_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command to get 24h stats
        Usage: /stats BTC/USDT
        """
        try:
            symbol = context.args[0].upper()
            stats = await self.binance_helper.get_24h_stats(symbol)
            await update.message.reply_text(f"24h stats for {symbol}:\n"
                                            f"High: ${stats['high']}\n"
                                            f"Low: ${stats['low']}\n"
                                            f"Volume: ${stats['volume']}\n"
                                            f"Price Change: ${stats['price_change']} ({stats['price_change_percent']}%)")
        except Exception as e:
            logger.error(f"Error handling stats command: {str(e)}")
            await update.message.reply_text("❌ Failed to get stats information.")

    async def get_5m_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /5mstats command to get 5m stats
        Usage: /5mstats BTC/USDT
        """
        try:
            symbol = context.args[0].upper()
            stats = await self.binance_helper.get_5m_stats(symbol)
            await update.message.reply_text(f"5m stats for {symbol}:\n"
                                            f"Open: ${stats['open']}\n"
                                            f"High: ${stats['high']}\n"
                                            f"Low: ${stats['low']}\n"
                                            f"Close: ${stats['close']}\n"
                                            f"Volume: ${stats['volume']}\n"
                                            f"Price Change: ${stats['price_change']} ({stats['price_change_percent']}%)\n"
                                            f"Number of Trades: {stats['number_of_trades']}\n"
                                            f"Taker Buy Volume: ${stats['taker_buy_volume']}\n"
                                            f"Taker Buy Quote Volume: ${stats['taker_buy_quote_volume']}")
        except Exception as e:
            logger.error(f"Error handling 5m stats command: {str(e)}")
            await update.message.reply_text("❌ Failed to get 5m stats information.")

    async def get_5m_price_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /5mpricehistory command to get 5m price history
        Usage: /5mpricehistory BTC/USDT
        """
        try:
            if not context.args or len(context.args) != 1:
                await update.message.reply_text("❌ Usage: /5mpricehistory SYMBOL\nExample: /5mpricehistory BTC/USDT")
                return

            symbol = context.args[0].upper()
            history = await self.binance_helper.get_5m_price_history(symbol)

            # Format the message in parts to avoid length issues
            header = f"📊 Price History for {symbol} (5m intervals)\n\n"
            await update.message.reply_text(header)

            # Send price history entries
            history_msg = "🕒 Historical Prices:\n"
            for entry in history['data']['history']:
                time_str = datetime.fromtimestamp(entry['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                change_symbol = "📈" if entry.get('price_change', 0) >= 0 else "📉"
                history_msg += (
                    f"\n⏰ {time_str}\n"
                    f"Close: ${entry['close']:,.5f}\n"
                    f"High: ${entry['high']:,.5f}\n"
                    f"Low: ${entry['low']:,.5f}\n"
                    f"Volume: {entry['volume']:,.3f}\n"
                )
                if entry.get('price_change', 0) != 0:
                    history_msg += f"Change: {change_symbol} ${entry['price_change']:+,.5f} ({entry['price_change_percent']:+.3f}%)\n"
                history_msg += f"Trades: {entry['number_of_trades']:,}\n"
                history_msg += "➖➖➖➖➖➖➖➖➖➖\n"

            await update.message.reply_text(history_msg)

            # Send statistics
            stats = history['data']['statistics']
            stats_msg = (
                "📈 Statistics Summary:\n\n"
                f"Mean Price: ${stats['mean_price']:,.5f}\n"
                f"Highest Price: ${stats['max_price']:,.5f}\n"
                f"Lowest Price: ${stats['min_price']:,.5f}\n"
                f"Total Change: ${stats['total_change']:+,.5f} ({stats['total_change_percent']:+.3f}%)\n"
                f"Volatility: {stats['volatility']:.3f}%\n\n"
                f"Last Updated: {datetime.fromtimestamp(history['data']['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')}"
            )

            await update.message.reply_text(stats_msg)

        except Exception as e:
            logger.error(f"Error handling 5m price history command: {str(e)}")
            await update.message.reply_text("❌ Failed to get 5m price history information.")

    async def with_concurrency_control(self, func, *args, **kwargs):
        """
        Execute a function with concurrency control to prevent overlap.

        Args:
            func: The async function to execute
            *args: Positional arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function

        Returns:
            The result of the function execution
        """
        if not self._semaphore:
            import asyncio
            self._semaphore = asyncio.Semaphore(1)

        async with self._semaphore:
            return await func(*args, **kwargs)

    # Decorator for command handlers to prevent overlapping execution
    def command_handler(self, func):
        """
        Decorator to add concurrency control and error handling to command handlers.

        Args:
            func: The command handler function to wrap

        Returns:
            Wrapped function with concurrency control and error handling
        """
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            try:
                return await self.with_concurrency_control(func, update, context)
            except Exception as e:
                logger.error(f"Error in command handler {func.__name__}: {str(e)}")
                # Try to notify the user
                try:
                    await update.message.reply_text(f"❌ An error occurred: {str(e)}")
                except:
                    pass

        return wrapper

    async def handle_swap_crypto_to_stable(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /swap_crypto command to swap cryptocurrency to stablecoin
        Usage: /swap_crypto SYMBOL AMOUNT
        Example: /swap_crypto BTC 0.01
        """
        try:
            if len(context.args) != 2:
                await update.message.reply_text("❌ Usage: /swap_crypto SYMBOL AMOUNT\nExample: /swap_crypto BTC 0.01")
                return

            symbol = context.args[0].upper()
            try:
                amount = float(context.args[1])
            except ValueError:
                await update.message.reply_text("❌ Amount must be a valid number")
                return

            # Check if amount is positive
            if amount <= 0:
                await update.message.reply_text("❌ Amount must be positive")
                return

            # Get current price of the symbol
            await update.message.reply_text(f"🔍 Getting price for {symbol}...")
            price_data = await self.binance_helper.get_price(symbol)
            current_price = price_data['price']

            # Get user from database
            user = await user_crud.get_by_telegram_id(self.db, telegram_id=update.effective_user.id)
            if not user:
                await update.message.reply_text("❌ Please start the bot first with /start")
                return

            # Execute swap
            await update.message.reply_text(f"💱 Swapping {amount} {symbol} to stablecoin...")

            # Ensure swap_service has DB session
            swap_service.db = self.db

            result = await swap_service.swap_symbol_stable_coin(
                symbol=symbol,
                quantity=amount,
                current_price=current_price
            )

            if result["status"] == "success":
                # Format success message
                transaction = result["transaction"]
                swap_msg = (
                    f"✅ *Swap Completed*\n\n"
                    f"From: {transaction['from_amount']} {transaction['from_symbol']}\n"
                    f"To: {transaction['to_amount']:,.2f} {transaction['to_symbol']}\n"
                    f"Rate: ${transaction['rate']:,.2f}\n"
                    f"Fee: ${transaction['fee_amount']:,.2f} ({transaction['fee_percentage']}%)\n"
                    f"Transaction ID: {transaction['transaction_id']}"
                )
                await update.message.reply_text(swap_msg, parse_mode='Markdown')
            else:
                await update.message.reply_text(f"❌ Swap failed: {result['message']}")

        except Exception as e:
            logger.error(f"Error handling swap_crypto command: {str(e)}")
            await update.message.reply_text(f"❌ Failed to execute swap: {str(e)}")

    async def handle_swap_stable_to_crypto(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /swap_stable command to swap stablecoin to cryptocurrency
        Usage: /swap_stable STABLE CRYPTO AMOUNT
        Example: /swap_stable USDT BTC 100
        """
        try:
            if len(context.args) != 3:
                await update.message.reply_text("❌ Usage: /swap_stable STABLE CRYPTO AMOUNT\nExample: /swap_stable USDT BTC 100")
                return

            stable_coin = context.args[0].upper()
            symbol = context.args[1].upper()
            try:
                amount = float(context.args[2])
            except ValueError:
                await update.message.reply_text("❌ Amount must be a valid number")
                return

            # Check if amount is positive
            if amount <= 0:
                await update.message.reply_text("❌ Amount must be positive")
                return

            # Get user from database
            user = await user_crud.get_by_telegram_id(self.db, telegram_id=update.effective_user.id)
            if not user:
                await update.message.reply_text("❌ Please start the bot first with /start")
                return

            # Execute swap
            await update.message.reply_text(f"💱 Swapping {amount} {stable_coin} to {symbol}...")

            # Ensure swap_service has DB session
            swap_service.db = self.db

            result = await swap_service.swap_stable_coin_symbol(
                stable_coin=stable_coin,
                symbol=symbol,
                amount=amount
            )

            if result["status"] == "success":
                # Format success message
                transaction = result["transaction"]
                swap_msg = (
                    f"✅ *Swap Completed*\n\n"
                    f"From: {transaction['from_amount']} {transaction['from_symbol']}\n"
                    f"To: {transaction['to_amount']:,.8f} {transaction['to_symbol']}\n"
                    f"Rate: ${transaction['rate']:,.2f}\n"
                    f"Fee: ${transaction['fee_amount']:,.2f} ({transaction['fee_percentage']}%)\n"
                    f"Transaction ID: {transaction['transaction_id']}"
                )
                await update.message.reply_text(swap_msg, parse_mode='Markdown')
            else:
                await update.message.reply_text(f"❌ Swap failed: {result['message']}")

        except Exception as e:
            logger.error(f"Error handling swap_stable command: {str(e)}")
            await update.message.reply_text(f"❌ Failed to execute swap: {str(e)}")

    async def get_swap_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /swap_history command
        Usage: /swap_history [LIMIT]
        Example: /swap_history 5
        """
        try:
            limit = 5  # Default limit

            if context.args and len(context.args) == 1:
                try:
                    limit = int(context.args[0])
                    if limit < 1:
                        limit = 1
                    elif limit > 10:
                        limit = 10
                except ValueError:
                    await update.message.reply_text("❌ Limit must be a valid number")
                    return

            # Get user from database
            user = await user_crud.get_by_telegram_id(self.db, telegram_id=update.effective_user.id)
            if not user:
                await update.message.reply_text("❌ Please start the bot first with /start")
                return

            # Fetch swap history from database
            from app.crud.crud_swap_transaction import swap_transaction_crud
            transactions = await swap_transaction_crud.get_multi(
                self.db,
                skip=0,
                limit=limit,
                filters={"user_id": user.id}
            )

            if not transactions:
                await update.message.reply_text("📊 No swap history found.")
                return

            # Format history message
            history_msg = "📊 *Swap Transaction History*\n\n"

            for tx in transactions:
                timestamp = tx.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                history_msg += (
                    f"ID: {tx.transaction_id}\n"
                    f"{tx.from_amount} {tx.from_symbol} → {tx.to_amount:,.8f} {tx.to_symbol}\n"
                    f"Rate: ${tx.rate:,.2f}\n"
                    f"Fee: ${tx.fee_amount:,.2f} ({tx.fee_percentage}%)\n"
                    f"Date: {timestamp}\n"
                    f"Status: {tx.status.upper()}\n\n"
                )

            await update.message.reply_text(history_msg, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error handling swap_history command: {str(e)}")
            await update.message.reply_text(f"❌ Failed to get swap history: {str(e)}")

def create_telegram_service(db: AsyncSession) -> TelegramService:
    """
    Create or get the singleton instance of TelegramService with all required dependencies.

    Args:
        db (AsyncSession): SQLAlchemy async database session

    Returns:
        TelegramService: Configured but not initialized service instance
    """
    try:
        logger.info("Getting TelegramService singleton instance...")



        # Get or create the singleton instance
        service = TelegramService.get_instance(
            db=db,
            market_analyzer=market_analyzer,
            portfolio_service=portfolio_service,
            straddle_service=straddle_service,
            binance_helper=binance_helper
        )

        logger.info("TelegramService singleton instance ready")
        return service
    except Exception as e:
        logger.error(f"Error creating TelegramService: {str(e)}")
        # Return the singleton instance even if there was an error setting up dependencies
        return TelegramService.get_instance(db=db)

# Create the singleton instance
telegram_service = TelegramService.get_instance()
