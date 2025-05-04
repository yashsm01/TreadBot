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
from ..core.config import settings
from ..models.telegram import TelegramUser, TelegramNotification
from ..crud.crud_telegram import telegram_user as user_crud
from ..crud.crud_telegram import telegram_notification as notification_crud
from ..services.market_analyzer import MarketAnalyzer
from ..services.portfolio_service import PortfolioService
from ..services.straddle_service import StraddleService
from ..services.helper.binance_helper import BinanceHelper
logger = logging.getLogger(__name__)

class TelegramService:
    def __init__(
        self,
        db: Session,
        market_analyzer: MarketAnalyzer,
        portfolio_service: PortfolioService,
        straddle_service: StraddleService,
        binance_helper: BinanceHelper
    ):
        self.db = db
        self.market_analyzer = market_analyzer
        self.portfolio_service = portfolio_service
        self.straddle_service = straddle_service
        self.binance_helper = binance_helper
        self.application = None
        self._initialized = False

    async def initialize(self):
        """Initialize the Telegram bot"""
        try:
            if not settings.TELEGRAM_BOT_TOKEN:
                logger.warning("No Telegram bot token provided. Telegram functionality will be disabled.")
                self._initialized = False
                return

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

            # Testing commands
            self.application.add_handler(CommandHandler("price", self.get_price))
            self.application.add_handler(CommandHandler("prices", self.get_multiple_prices))
            self.application.add_handler(CommandHandler("24hstats", self.get_24h_stats))
            self.application.add_handler(CommandHandler("5mstats", self.get_5m_stats))
            self.application.add_handler(CommandHandler("5mpricehistory", self.get_5m_price_history))
            # Add fallback handler for unknown commands
            self.application.add_handler(MessageHandler(filters.COMMAND, self._handle_unknown_command))

            await self.application.initialize()
            await self.application.start()

            # Start polling for updates
            await self.application.updater.start_polling()

            self._initialized = True
            logger.info("Telegram bot initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Telegram bot: {str(e)}")
            self._initialized = False
            # Don't raise the exception, just continue without Telegram functionality
            return

    async def stop(self):
        """Stop the Telegram bot"""
        if self.application:
            if self.application.updater:
                await self.application.updater.stop()
            await self.application.stop()
            logger.info("Telegram bot stopped")
            self._initialized = False

    async def send_notification(
        self,
        user_id: int,
        message_type: str,
        content: str,
        symbol: Optional[str] = None
    ):
        """Send notification to user"""
        try:
            notification = TelegramNotification(
                user_id=user_id,
                message_type=message_type,
                symbol=symbol,
                content=content
            )
            notification_crud.create(self.db, obj_in=notification)

            user = user_crud.get_by_telegram_id(self.db, telegram_id=user_id)
            if user and user.is_active:
                await self.application.bot.send_message(
                    chat_id=user.chat_id,
                    text=content,
                    parse_mode='Markdown'
                )
                notification.is_sent = True
                self.db.commit()
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            notification.error_message = str(e)
            self.db.commit()

    # Command Handlers
    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            # Check if user already exists
            existing_user = user_crud.get_by_telegram_id(self.db, telegram_id=update.effective_user.id)

            if existing_user:
                # Update existing user
                existing_user.is_active = True
                existing_user.last_interaction = datetime.utcnow()
                self.db.commit()
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
                user_crud.create(self.db, obj_in=user)
                welcome_msg = (
                    "🤖 Welcome to the Crypto Trading Bot!\n\n"
                    "Use /help to see available commands.\n"
                    "Your notifications are now active."
                )

            await update.message.reply_text(welcome_msg)
        except Exception as e:
            logger.error(f"Error handling start command: {str(e)}")
            await update.message.reply_text("❌ Failed to start bot. Please try again.")

    async def _handle_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command"""
        try:
            user = user_crud.get_by_telegram_id(self.db, telegram_id=update.effective_user.id)
            if user:
                user.is_active = False
                self.db.commit()
                await update.message.reply_text("🔕 Notifications stopped. Use /start to reactivate.")
        except Exception as e:
            logger.error(f"Error handling stop command: {str(e)}")
            await update.message.reply_text("❌ Failed to stop notifications.")

    async def _handle_update_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /update command"""
        try:
            user = user_crud.get_by_telegram_id(self.db, telegram_id=update.effective_user.id)
            if user:
                user.last_interaction = datetime.utcnow()
                self.db.commit()
                await update.message.reply_text("✅ User information updated successfully.")
        except Exception as e:
            logger.error(f"Error handling update command: {str(e)}")
            await update.message.reply_text("❌ Failed to update user information.")

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        try:
            user = user_crud.get_by_telegram_id(self.db, telegram_id=update.effective_user.id)
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
"""
        await update.message.reply_text(help_msg)

    async def handle_buy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /buy command"""
        try:
            if len(context.args) not in [2, 3]:
                await update.message.reply_text("❌ Usage: /buy SYMBOL QUANTITY [PRICE]\nExample: /buy BTC/USDT 0.1 50000")
                return

            # Get user from database
            user = user_crud.get_by_telegram_id(self.db, telegram_id=update.effective_user.id)
            if not user:
                await update.message.reply_text("❌ Please start the bot first with /start")
                return

            symbol = context.args[0].upper()
            quantity = float(context.args[1])

            # Get current market price if price not provided
            if len(context.args) == 3:
                price = float(context.args[2])
            else:
                market_data = await self.market_analyzer.get_market_analysis(symbol)
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
            user = user_crud.get_by_telegram_id(self.db, telegram_id=update.effective_user.id)
            if not user:
                await update.message.reply_text("❌ Please start the bot first with /start")
                return

            symbol = context.args[0].upper()
            quantity = float(context.args[1])

            # Get current market price if price not provided
            if len(context.args) == 3:
                price = float(context.args[2])
            else:
                market_data = await self.market_analyzer.get_market_analysis(symbol)
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
                    f"Close: ${entry['close']:,.2f}\n"
                    f"High: ${entry['high']:,.2f}\n"
                    f"Low: ${entry['low']:,.2f}\n"
                    f"Volume: {entry['volume']:,.3f}\n"
                )
                if entry.get('price_change', 0) != 0:
                    history_msg += f"Change: {change_symbol} ${entry['price_change']:+,.2f} ({entry['price_change_percent']:+.2f}%)\n"
                history_msg += f"Trades: {entry['number_of_trades']:,}\n"
                history_msg += "➖➖➖➖➖➖➖➖➖➖\n"

            await update.message.reply_text(history_msg)

            # Send statistics
            stats = history['data']['statistics']
            stats_msg = (
                "📈 Statistics Summary:\n\n"
                f"Mean Price: ${stats['mean_price']:,.2f}\n"
                f"Highest Price: ${stats['max_price']:,.2f}\n"
                f"Lowest Price: ${stats['min_price']:,.2f}\n"
                f"Total Change: ${stats['total_change']:+,.2f} ({stats['total_change_percent']:+.2f}%)\n"
                f"Volatility: {stats['volatility']:.2f}%\n\n"
                f"Last Updated: {datetime.fromtimestamp(history['data']['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')}"
            )

            await update.message.reply_text(stats_msg)

        except Exception as e:
            logger.error(f"Error handling 5m price history command: {str(e)}")
            await update.message.reply_text("❌ Failed to get 5m price history information.")

def create_telegram_service(db: Session) -> TelegramService:
    """Create a new instance of TelegramService with all required dependencies"""
    market_analyzer = MarketAnalyzer()
    portfolio_service = PortfolioService(db)
    straddle_service = StraddleService(db)
    binance_helper = BinanceHelper()
    return TelegramService(
        db=db,
        market_analyzer=market_analyzer,
        portfolio_service=portfolio_service,
        straddle_service=straddle_service,
        binance_helper=binance_helper
    )

# Initialize as None, will be created properly in main.py

telegram_service = None
