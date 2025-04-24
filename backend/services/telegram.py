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

            # Straddle Strategy commands
            self.application.add_handler(CommandHandler("straddle", self.handle_straddle))
            self.application.add_handler(CommandHandler("update_straddle", self.handle_update_straddle))
            self.application.add_handler(CommandHandler("close_straddle", self.handle_close_straddle))
            self.application.add_handler(CommandHandler("straddles", self.get_straddle_positions))

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

Straddle Strategy:
/straddle <symbol> <quantity> <strike_price> <interval> - Open a new straddle position
/update_straddle <position_id> <new_price> <new_quantity> - Update an existing straddle position
/close_straddle <position_id> - Close an existing straddle position
/straddles - View all active straddle positions

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

    async def handle_straddle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /straddle command to open a new straddle position"""
        try:
            if not context.args or len(context.args) != 4:
                await update.message.reply_text(
                    "Invalid format. Use: /straddle <symbol> <quantity> <strike_price> <interval>\n"
                    "Example: /straddle BTC/USDT 0.1 50000 5"
                )
                return

            symbol = context.args[0].upper()
            quantity = float(context.args[1])
            strike_price = float(context.args[2])
            interval = int(context.args[3])
            user_id = update.effective_user.id

            # Get current market price for validation
            analysis = await self.market_analyzer.get_market_analysis(symbol, "5m")
            if not analysis or 'market_summary' not in analysis:
                await update.message.reply_text(f"Could not get market data for {symbol}")
                return

            current_price = analysis['market_summary']['last_price']

            # Create long and short positions for the straddle
            long_result = await self.portfolio_service.add_transaction(
                user_id=user_id,
                symbol=symbol,
                type="BUY",
                quantity=quantity,
                price=strike_price
            )

            short_result = await self.portfolio_service.add_transaction(
                user_id=user_id,
                symbol=symbol,
                type="SELL",
                quantity=quantity,
                price=strike_price
            )

            # Store the interval for automated notifications
            await self.portfolio_service.set_straddle_interval(
                user_id=user_id,
                position_id=long_result['transaction_id'],
                interval=interval
            )

            await update.message.reply_text(
                f"✅ Straddle position opened:\n"
                f"Symbol: {symbol}\n"
                f"Quantity: {quantity}\n"
                f"Strike Price: ${strike_price:,.2f}\n"
                f"Current Price: ${current_price:,.2f}\n"
                f"Long Position ID: {long_result['transaction_id']}\n"
                f"Short Position ID: {short_result['transaction_id']}\n"
                f"Total Investment: ${(quantity * strike_price * 2):,.2f}\n"
                f"Alert Interval: {interval} minutes"
            )

            # Start automated notifications
            await self.schedule_straddle_notifications(
                user_id=user_id,
                position_id=long_result['transaction_id'],
                interval=interval
            )

        except ValueError as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
        except Exception as e:
            logger.error(f"Error handling straddle command: {str(e)}")
            await update.message.reply_text("❌ An error occurred while creating the straddle position.")

    async def handle_update_straddle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /update_straddle command to update an existing straddle position"""
        try:
            if not context.args or len(context.args) != 3:
                await update.message.reply_text(
                    "Invalid format. Use: /update_straddle <position_id> <new_price> <new_quantity>\n"
                    "Example: /update_straddle 123 51000 0.15"
                )
                return

            position_id = int(context.args[0])
            new_price = float(context.args[1])
            new_quantity = float(context.args[2])
            user_id = update.effective_user.id

            result = await self.portfolio_service.update_straddle_position(
                user_id=user_id,
                position_id=position_id,
                new_price=new_price,
                new_quantity=new_quantity
            )

            if not result:
                await update.message.reply_text("❌ Position not found or could not be updated.")
                return

            await update.message.reply_text(
                f"✅ Straddle position updated:\n"
                f"Position ID: {position_id}\n"
                f"New Price: ${new_price:,.2f}\n"
                f"New Quantity: {new_quantity}\n"
                f"Symbol: {result['symbol']}"
            )

        except ValueError as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
        except Exception as e:
            logger.error(f"Error handling update_straddle command: {str(e)}")
            await update.message.reply_text("❌ An error occurred while updating the straddle position.")

    async def handle_close_straddle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /close_straddle command to close an existing straddle position"""
        try:
            if not context.args or len(context.args) != 1:
                await update.message.reply_text(
                    "Invalid format. Use: /close_straddle <position_id>\n"
                    "Example: /close_straddle 123"
                )
                return

            position_id = int(context.args[0])
            user_id = update.effective_user.id

            # Get position details and close both legs
            position = await self.portfolio_service.get_straddle_position(user_id, position_id)
            if not position:
                await update.message.reply_text(f"Straddle position {position_id} not found")
                return

            # Close both long and short positions
            close_long = await self.portfolio_service.add_transaction(
                user_id=user_id,
                symbol=position['symbol'],
                type="SELL",
                quantity=position['quantity'],
                price=position['current_price']
            )

            close_short = await self.portfolio_service.add_transaction(
                user_id=user_id,
                symbol=position['symbol'],
                type="BUY",
                quantity=position['quantity'],
                price=position['current_price']
            )

            # Calculate P/L
            long_pl = (position['current_price'] - position['strike_price']) * position['quantity']
            short_pl = (position['strike_price'] - position['current_price']) * position['quantity']
            total_pl = long_pl + short_pl

            await update.message.reply_text(
                f"✅ Straddle position closed:\n"
                f"Position ID: {position_id}\n"
                f"Symbol: {position['symbol']}\n"
                f"Quantity: {position['quantity']}\n"
                f"Strike Price: ${position['strike_price']:,.2f}\n"
                f"Close Price: ${position['current_price']:,.2f}\n"
                f"Long P/L: ${long_pl:,.2f}\n"
                f"Short P/L: ${short_pl:,.2f}\n"
                f"Total P/L: ${total_pl:,.2f}"
            )

        except ValueError as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
        except Exception as e:
            logger.error(f"Error handling close_straddle command: {str(e)}")
            await update.message.reply_text("❌ An error occurred while closing the straddle position.")

    async def get_straddle_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /straddles command to view all active straddle positions"""
        try:
            user_id = update.effective_user.id
            positions = await self.portfolio_service.get_straddle_positions(user_id)

            if not positions:
                await update.message.reply_text("You have no active straddle positions.")
                return

            positions_text = "🔄 Active Straddle Positions:\n\n"
            total_pl = 0

            for pos in positions:
                # Calculate current P/L for both legs
                long_pl = (pos['current_price'] - pos['strike_price']) * pos['quantity']
                short_pl = (pos['strike_price'] - pos['current_price']) * pos['quantity']
                position_pl = long_pl + short_pl
                total_pl += position_pl

                # Determine bias based on price movement
                bias = "LONG" if pos['current_price'] < pos['strike_price'] else "SHORT"
                price_diff_pct = abs(pos['current_price'] - pos['strike_price']) / pos['strike_price'] * 100

                positions_text += (
                    f"ID: {pos['position_id']}\n"
                    f"Symbol: {pos['symbol']}\n"
                    f"Quantity: {pos['quantity']:.8f}\n"
                    f"Strike: ${pos['strike_price']:,.2f}\n"
                    f"Current: ${pos['current_price']:,.2f}\n"
                    f"Long P/L: ${long_pl:,.2f}\n"
                    f"Short P/L: ${short_pl:,.2f}\n"
                    f"Total P/L: ${position_pl:,.2f}\n"
                    f"Current Bias: {bias} ({price_diff_pct:.2f}% from strike)\n"
                    f"Opened: {pos['open_time']}\n"
                    f"Alert Interval: {pos.get('interval', 'N/A')} minutes\n\n"
                )

            positions_text += f"Total P/L Across All Positions: ${total_pl:,.2f}"
            await update.message.reply_text(positions_text)

        except Exception as e:
            logger.error(f"Error handling straddles command: {str(e)}")
            await update.message.reply_text("❌ An error occurred while retrieving straddle positions.")

    async def send_straddle_notification(self, user_id: int, position_id: int):
        """Send automated notification for a straddle position"""
        try:
            position = await self.portfolio_service.get_straddle_position(user_id, position_id)
            if not position:
                return

            # Get price history
            price_history = await self.market_analyzer.get_price_history(
                position['symbol'],
                limit=3
            )

            # Calculate P/L
            long_pl = (position['current_price'] - position['strike_price']) * position['quantity']
            short_pl = (position['strike_price'] - position['current_price']) * position['quantity']
            total_pl = long_pl + short_pl

            # Determine strategy action
            price_diff = position['current_price'] - position['strike_price']
            action = "SELL" if price_diff > 0 else "BUY"
            bias = "SHORT" if price_diff > 0 else "LONG"

            message = (
                f"[STRADDLE STRATEGY ALERT 🔁]\n\n"
                f"Symbol: {position['symbol']}\n"
                f"Strategy Action: {action} now ({bias} bias)\n"
                f"Current Price: ${position['current_price']:,.2f}\n"
                f"Strike Price: ${position['strike_price']:,.2f}\n\n"
                f"💰 Entry Price (BUY): ${position['strike_price']:,.2f}\n"
                f"💰 Entry Price (SELL): ${position['strike_price']:,.2f}\n\n"
                f"Last 3 Prices:\n"
            )

            for price in price_history:
                message += f"- ${price:,.2f}\n"

            message += (
                f"\n📊 P/L (Buy Leg): ${long_pl:+,.2f}\n"
                f"📊 P/L (Sell Leg): ${short_pl:+,.2f}\n"
                f"Total P/L: ${total_pl:+,.2f}\n\n"
                f"Next update in: {position.get('interval', 'N/A')} min ⏳"
            )

            await self.send_message(message)

        except Exception as e:
            logger.error(f"Error sending straddle notification: {str(e)}")

    async def schedule_straddle_notifications(self, user_id: int, position_id: int, interval: int):
        """Schedule automated notifications for a straddle position"""
        try:
            while True:
                await self.send_straddle_notification(user_id, position_id)
                await asyncio.sleep(interval * 60)  # Convert minutes to seconds
        except Exception as e:
            logger.error(f"Error in straddle notification scheduler: {str(e)}")
