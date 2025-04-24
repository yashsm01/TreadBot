import logging
import os
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from ..analysis.market_analyzer import MarketAnalyzer
from ..trader.exchange_manager import ExchangeManager
import asyncio
from ..services.portfolio import PortfolioService

logger = logging.getLogger(__name__)

class TelegramService:
    def __init__(self, market_analyzer: MarketAnalyzer, portfolio_service: PortfolioService):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.market_analyzer = market_analyzer
        self.exchange_manager = None
        self.application = None
        self.bot = None
        self.portfolio_service = portfolio_service
        self._initialized = False

    async def initialize(self):
        """Initialize the Telegram bot and set up command handlers"""
        if self._initialized:
            return

        try:
            if not self.token or not self.chat_id:
                logger.warning("Telegram bot token or chat ID not set. Telegram notifications will be disabled.")
                return

            # Initialize bot first
            self.bot = Bot(token=self.token)

            # Build application
            self.application = Application.builder().token(self.token).build()

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

            # Initialize and start polling in the background
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

            self._initialized = True
            logger.info("Telegram bot started successfully")

            # Send startup notification
            await self.send_message("🤖 Trading Bot is now online and ready!")
        except Exception as e:
            logger.error(f"Error initializing Telegram bot: {str(e)}")
            self._initialized = False
            # Don't raise the exception - allow the application to continue without Telegram

    async def stop(self):
        """Stop the Telegram service"""
        if not self._initialized:
            return

        try:
            if self.application:
                await self.send_message("🔴 Trading Bot is shutting down...")
                await self.application.stop()
                await self.application.shutdown()
                self._initialized = False
                logger.info("Telegram bot stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping Telegram bot: {str(e)}")

    async def send_message(self, message: str, parse_mode: str = None) -> bool:
        """Base method for sending messages"""
        if not self._initialized or not self.bot or not self.chat_id:
            return False

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {str(e)}")
            return False

    async def send_error_notification(self, error_message: str, error_details: dict = None):
        """Send error notification"""
        if not self._initialized:
            return False

        try:
            message = f"🚨 Error Alert:\n{error_message}"
            if error_details:
                message += "\n\nDetails:"
                for key, value in error_details.items():
                    message += f"\n{key}: {value}"

            return await self.send_message(message)
        except Exception as e:
            logger.error(f"Failed to send error notification: {str(e)}")
            return False

    async def send_test_notification(self) -> bool:
        """Send test notification"""
        if not self._initialized:
            return False

        try:
            message = "🔔 Test notification from Crypto Trading Bot\n\nIf you see this message, the bot is working correctly!"
            return await self.send_message(message)
        except Exception as e:
            logger.error(f"Failed to send test notification: {str(e)}")
            return False

    async def send_trade_notification(self, strategy_type: str, symbol: str, entry_price: float, quantity: float):
        """Send trade notification"""
        if not self._initialized:
            return False

        try:
            message = (
                f"🔔 New Trade Alert\n\n"
                f"Strategy: {strategy_type}\n"
                f"Symbol: {symbol}\n"
                f"Entry Price: ${entry_price:,.2f}\n"
                f"Quantity: {quantity:,.8f}\n"
                f"Total Value: ${entry_price * quantity:,.2f}"
            )
            return await self.send_message(message)
        except Exception as e:
            logger.error(f"Failed to send trade notification: {str(e)}")
            return False

    async def send_daily_summary(self, summary: dict):
        """Send daily trading summary"""
        if not self._initialized:
            return False

        try:
            message = "📊 Daily Trading Summary\n\n"
            message += f"Total Trades: {summary['total_trades']}\n"
            message += f"Winning Trades: {summary['winning_trades']}\n"
            message += f"Losing Trades: {summary['losing_trades']}\n"
            message += f"Net Profit: {summary['net_profit']:+.2f}%\n\n"

            if summary.get('best_trade'):
                message += f"Best Trade: {summary['best_trade']:+.2f}%\n"
            if summary.get('worst_trade'):
                message += f"Worst Trade: {summary['worst_trade']:+.2f}%\n\n"

            if summary.get('trades'):
                message += "Recent Trades:\n"
                for trade in summary['trades'][:5]:  # Show last 5 trades
                    message += f"- {trade['symbol']}: {trade['profit_pct']:+.2f}% "
                    message += f"(${trade['entry_price']:,.2f} → ${trade['exit_price']:,.2f})\n"

            return await self.send_message(message)
        except Exception as e:
            logger.error(f"Failed to send daily summary: {str(e)}")
            return False

    async def get_pairs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pairs command"""
        try:
            pairs = await self.market_analyzer._update_supported_pairs()
            pairs = self.market_analyzer.get_supported_pairs()
            if pairs:
                message = "Available trading pairs:\n" + "\n".join(pairs)
            else:
                message = "No trading pairs available"
            await update.message.reply_text(message)
        except Exception as e:
            logger.error(f"Error handling /pairs command: {str(e)}")
            await update.message.reply_text("Failed to get trading pairs")

    async def get_analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /analysis command"""
        try:
            if not context.args or len(context.args) < 1:
                await update.message.reply_text("Usage: /analysis SYMBOL [TIMEFRAME]\nExample: /analysis BTC/USDT 5m")
                return

            symbol = context.args[0].upper()
            timeframe = context.args[1] if len(context.args) > 1 else "5m"

            analysis = await self.market_analyzer.get_market_analysis(symbol, timeframe)
            if not analysis:
                await update.message.reply_text(f"No analysis available for {symbol}")
                return

            # Format the analysis message
            message = f"Market Analysis for {symbol} ({timeframe}):\n\n"

            if 'market_summary' in analysis:
                summary = analysis['market_summary']
                message += f"Price: ${summary['last_price']:,.2f}\n"
                message += f"24h Change: {summary['price_change_24h']:+.2f}%\n"
                message += f"24h Volume: ${summary['volume_24h']:,.2f}\n\n"

            if 'trading_signals' in analysis:
                signals = analysis['trading_signals']
                message += f"Trend: {signals['trend'].upper()}\n"
                message += f"Momentum: {signals['momentum']:+.2f}%\n"
                message += f"Volume Ratio: {signals['volume_ratio']:.2f}x\n\n"

            if 'volatility_metrics' in analysis:
                volatility = analysis['volatility_metrics']
                message += f"Volatility: {volatility['volatility']*100:.2f}%\n"
                message += f"Price Range: {volatility['price_range']*100:.2f}%\n"

            await update.message.reply_text(message)
        except Exception as e:
            logger.error(f"Error handling /analysis command: {str(e)}")
            await update.message.reply_text(f"Error analyzing {symbol}: {str(e)}")

    async def get_signals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /signals command"""
        try:
            if not context.args or len(context.args) < 1:
                await update.message.reply_text("Usage: /signals SYMBOL [TIMEFRAME]\nExample: /signals BTC/USDT 1h")
                return

            symbol = context.args[0].upper()
            timeframe = context.args[1] if len(context.args) > 1 else "1h"

            signals = await self.market_analyzer.get_trading_signals(symbol, timeframe)
            if not signals:
                await update.message.reply_text(f"No signals available for {symbol}")
                return

            message = f"Trading Signals for {symbol} ({timeframe}):\n\n"
            message += f"Current Price: ${signals['current_price']:,.2f}\n"
            message += f"Trend: {signals['trend'].upper()}\n"
            message += f"SMA20: ${signals['sma20']:,.2f}\n"
            message += f"SMA50: ${signals['sma50']:,.2f}\n"
            message += f"Momentum: {signals['momentum']:+.2f}%\n"
            message += f"Volume Ratio: {signals['volume_ratio']:.2f}x\n"

            await update.message.reply_text(message)
        except Exception as e:
            logger.error(f"Error handling /signals command: {str(e)}")
            await update.message.reply_text(f"Error getting signals for {symbol}: {str(e)}")

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send help message with available commands"""
        help_text = """
Available commands:
Trading:
/pairs - List available trading pairs
/analysis <symbol> - Get market analysis for a symbol (e.g. /analysis BTC/USDT)
/signals <symbol> - Get trading signals for a symbol (e.g. /signals BTC/USDT)

Portfolio:
/buy <symbol> <quantity> <price> - Add a buy transaction (e.g. /buy BTC/USDT 0.1 50000)
/sell <symbol> <quantity> <price> - Add a sell transaction (e.g. /sell BTC/USDT 0.1 51000)
/portfolio - View your current portfolio
/history [symbol] - View transaction history (optional: filter by symbol)
/profit [timeframe] - View profit summary (timeframe: daily/weekly/monthly/all)

Other:
/start - Start the bot
/help - Show this help message
"""
        await update.message.reply_text(help_text)

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            chat_id = update.message.chat_id
            user_id = update.message.from_user.id

            # Add user to active users list or database
            message = (
                "🤖 Welcome to the Crypto Trading Bot!\n\n"
                "I will help you monitor your trades and provide market analysis.\n"
                "Use /help to see available commands."
            )
            await update.message.reply_text(message)
            logger.info(f"New user started the bot: {user_id}")
        except Exception as e:
            logger.error(f"Error handling start command: {str(e)}")
            await update.message.reply_text("Failed to start the bot. Please try again.")

    async def _handle_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command"""
        try:
            chat_id = update.message.chat_id
            user_id = update.message.from_user.id

            # Remove user from active users list or database
            message = "Bot stopped. You will no longer receive notifications.\nUse /start to enable the bot again."
            await update.message.reply_text(message)
            logger.info(f"User stopped the bot: {user_id}")
        except Exception as e:
            logger.error(f"Error handling stop command: {str(e)}")
            await update.message.reply_text("Failed to stop the bot. Please try again.")

    async def _handle_update_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /update command"""
        try:
            if not context.args or len(context.args) < 2:
                await update.message.reply_text(
                    "Usage: /update PARAMETER VALUE\n"
                    "Example: /update interval 5m\n\n"
                    "Available parameters:\n"
                    "- interval (1m, 5m, 15m, 30m, 1h, 4h, 1d)\n"
                    "- breakout_pct (e.g., 0.5)\n"
                    "- tp_pct (take profit percentage)\n"
                    "- sl_pct (stop loss percentage)\n"
                    "- quantity (trade size)"
                )
                return

            param = context.args[0].lower()
            value = context.args[1]

            # Validate and update parameter
            # This is a placeholder - implement actual parameter updating logic
            message = f"Updated {param} to {value}"
            await update.message.reply_text(message)
            logger.info(f"User {update.message.from_user.id} updated {param} to {value}")
        except Exception as e:
            logger.error(f"Error handling update command: {str(e)}")
            await update.message.reply_text("Failed to update parameter. Please check the format and try again.")

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        try:
            # Get current trading status
            # This is a placeholder - implement actual status checking logic
            status = {
                "active": True,
                "current_trades": 0,
                "last_trade_time": "No trades yet",
                "trading_pairs": self.market_analyzer.get_supported_pairs() if self.market_analyzer else []
            }

            message = "📊 Trading Bot Status\n\n"
            message += f"Active: {'✅' if status['active'] else '❌'}\n"
            message += f"Current Trades: {status['current_trades']}\n"
            message += f"Last Trade: {status['last_trade_time']}\n"
            message += f"Trading Pairs: {len(status['trading_pairs'])}\n"

            await update.message.reply_text(message)
        except Exception as e:
            logger.error(f"Error handling status command: {str(e)}")
            await update.message.reply_text("Failed to get bot status. Please try again.")

    async def _handle_user_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle non-command user input"""
        try:
            text = update.message.text
            chat_id = update.message.chat_id
            user_id = update.message.from_user.id

            # This is a placeholder - implement actual user input handling logic
            await update.message.reply_text(
                "I can only respond to commands. Use /help to see available commands."
            )
        except Exception as e:
            logger.error(f"Error handling user input: {str(e)}")
            await update.message.reply_text("Failed to process your input. Please try again.")

    async def handle_buy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle buy command: /buy <symbol> <quantity> <price>"""
        try:
            if len(context.args) != 3:
                await update.message.reply_text(
                    "Invalid format. Use: /buy <symbol> <quantity> <price>\n"
                    "Example: /buy BTC/USDT 0.1 50000"
                )
                return

            symbol = context.args[0].upper()
            quantity = float(context.args[1])
            price = float(context.args[2])
            user_id = update.effective_user.id

            result = await self.portfolio_service.add_transaction(
                user_id=user_id,
                symbol=symbol,
                type="BUY",
                quantity=quantity,
                price=price
            )

            await update.message.reply_text(
                f"✅ Buy order recorded:\n"
                f"Symbol: {result['symbol']}\n"
                f"Quantity: {result['quantity']}\n"
                f"Price: ${result['price']:,.2f}\n"
                f"Total: ${result['total']:,.2f}"
            )
        except ValueError as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
        except Exception as e:
            logger.error(f"Error handling buy command: {str(e)}")
            await update.message.reply_text("❌ An error occurred while processing your request.")

    async def handle_sell(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle sell command: /sell <symbol> <quantity> <price>"""
        try:
            if len(context.args) != 3:
                await update.message.reply_text(
                    "Invalid format. Use: /sell <symbol> <quantity> <price>\n"
                    "Example: /sell BTC/USDT 0.1 51000"
                )
                return

            symbol = context.args[0].upper()
            quantity = float(context.args[1])
            price = float(context.args[2])
            user_id = update.effective_user.id

            result = await self.portfolio_service.add_transaction(
                user_id=user_id,
                symbol=symbol,
                type="SELL",
                quantity=quantity,
                price=price
            )

            await update.message.reply_text(
                f"✅ Sell order recorded:\n"
                f"Symbol: {result['symbol']}\n"
                f"Quantity: {result['quantity']}\n"
                f"Price: ${result['price']:,.2f}\n"
                f"Total: ${result['total']:,.2f}"
            )
        except ValueError as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
        except Exception as e:
            logger.error(f"Error handling sell command: {str(e)}")
            await update.message.reply_text("❌ An error occurred while processing your request.")

    async def get_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle portfolio command to show current holdings"""
        try:
            user_id = update.effective_user.id
            portfolio = await self.portfolio_service.get_portfolio(user_id)

            if not portfolio['portfolio']:
                await update.message.reply_text("Your portfolio is empty.")
                return

            # Format portfolio items
            portfolio_text = "📊 Your Portfolio:\n\n"
            for item in portfolio['portfolio']:
                portfolio_text += (
                    f"*{item['symbol']}*\n"
                    f"Quantity: {item['quantity']:.8f}\n"
                    f"Avg Buy: ${item['avg_buy_price']:,.2f}\n"
                    f"Current: ${item['current_price']:,.2f}\n"
                    f"Value: ${item['current_value']:,.2f}\n"
                    f"P/L: ${item['profit_loss']:,.2f} ({item['profit_loss_pct']:,.2f}%)\n\n"
                )

            # Add summary
            summary = portfolio['summary']
            portfolio_text += (
                f"*Portfolio Summary:*\n"
                f"Total Invested: ${summary['total_invested']:,.2f}\n"
                f"Current Value: ${summary['total_current_value']:,.2f}\n"
                f"Total P/L: ${summary['total_profit_loss']:,.2f} ({summary['total_profit_loss_pct']:,.2f}%)"
            )

            await update.message.reply_text(portfolio_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error handling portfolio command: {str(e)}")
            await update.message.reply_text("❌ An error occurred while retrieving your portfolio.")

    async def get_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle history command to show transaction history"""
        try:
            user_id = update.effective_user.id
            symbol = context.args[0].upper() if context.args else None

            transactions = await self.portfolio_service.get_transaction_history(user_id, symbol)

            if not transactions:
                await update.message.reply_text(
                    "No transactions found." if not symbol
                    else f"No transactions found for {symbol}."
                )
                return

            history_text = f"📜 Transaction History{f' for {symbol}' if symbol else ''}:\n\n"
            for tx in transactions:
                history_text += (
                    f"*{tx['type']}* {tx['symbol']}\n"
                    f"Quantity: {tx['quantity']:.8f}\n"
                    f"Price: ${tx['price']:,.2f}\n"
                    f"Total: ${tx['total']:,.2f}\n"
                    f"Date: {tx['timestamp']}\n\n"
                )

            await update.message.reply_text(history_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error handling history command: {str(e)}")
            await update.message.reply_text("❌ An error occurred while retrieving transaction history.")

    async def get_profit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle profit command to show profit/loss summary"""
        try:
            user_id = update.effective_user.id
            timeframe = context.args[0].lower() if context.args else 'all'

            if timeframe not in ['daily', 'weekly', 'monthly', 'all']:
                await update.message.reply_text(
                    "Invalid timeframe. Use: daily, weekly, monthly, or all"
                )
                return

            summary = await self.portfolio_service.get_profit_summary(user_id, timeframe)

            profit_text = (
                f"💰 Profit Summary ({timeframe}):\n\n"
                f"Total Invested: ${summary['total_invested']:,.2f}\n"
                f"Current Value: ${summary['total_current_value']:,.2f}\n"
                f"Total P/L: ${summary['total_profit_loss']:,.2f} ({summary['total_profit_loss_pct']:,.2f}%)\n"
                f"Total Trades: {summary['total_trades']}\n"
                f"Last Updated: {summary['timestamp']}"
            )

            await update.message.reply_text(profit_text)
        except Exception as e:
            logger.error(f"Error handling profit command: {str(e)}")
            await update.message.reply_text("❌ An error occurred while retrieving profit summary.")
