import logging
from typing import Dict, Optional
from datetime import datetime
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from sqlalchemy.orm import Session
from ..core.config import settings
from ..models.telegram import TelegramUser, TelegramNotification
from ..crud.crud_telegram import telegram_crud
from ..services.market_analyzer import market_analyzer
from ..services.portfolio_service import portfolio_service

logger = logging.getLogger(__name__)

class TelegramService:
    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.bot: Optional[Bot] = None
        self.application: Optional[Application] = None
        self._initialized = False

    async def initialize(self, db: Session):
        """Initialize the Telegram bot and set up command handlers"""
        if self._initialized:
            return

        try:
            if not self.token:
                logger.warning("Telegram bot token not set. Telegram notifications will be disabled.")
                return

            # Initialize bot
            self.bot = Bot(token=self.token)
            self.application = Application.builder().token(self.token).build()

            # Add command handlers
            self.application.add_handler(CommandHandler("start", self._handle_start))
            self.application.add_handler(CommandHandler("help", self._handle_help))
            self.application.add_handler(CommandHandler("analysis", self._handle_analysis))
            self.application.add_handler(CommandHandler("portfolio", self._handle_portfolio))
            self.application.add_handler(CommandHandler("signals", self._handle_signals))

            # Initialize and start polling
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()

            self._initialized = True
            logger.info("Telegram bot started successfully")

        except Exception as e:
            logger.error(f"Error initializing Telegram bot: {str(e)}")
            raise

    async def stop(self):
        """Stop the Telegram service"""
        try:
            if self.application:
                await self.application.stop()
                await self.application.shutdown()
                self._initialized = False
                logger.info("Telegram bot stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping Telegram bot: {str(e)}")

    async def send_notification(self, db: Session, user_id: int, message_type: str, content: str, symbol: Optional[str] = None):
        """Send notification to user"""
        try:
            # Create notification record
            notification = await telegram_crud.create_notification(
                db=db,
                user_id=user_id,
                message_type=message_type,
                content=content,
                symbol=symbol
            )

            # Get user's chat ID
            user = await telegram_crud.get_user_by_telegram_id(db, user_id)
            if not user:
                raise ValueError(f"Telegram user {user_id} not found")

            # Send message
            await self.bot.send_message(
                chat_id=user.chat_id,
                text=content,
                parse_mode='Markdown'
            )

            # Update notification status
            await telegram_crud.mark_notification_sent(db, notification.id)

        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            if notification:
                await telegram_crud.update_notification_error(db, notification.id, str(e))

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            message = (
                "🤖 Welcome to the Crypto Trading Bot!\n\n"
                "Available commands:\n"
                "/help - Show available commands\n"
                "/analysis <symbol> - Get market analysis\n"
                "/portfolio - View your portfolio\n"
                "/signals <symbol> - Get trading signals"
            )
            await update.message.reply_text(message)
        except Exception as e:
            logger.error(f"Error handling start command: {str(e)}")

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        try:
            help_text = """
Available Commands:
/analysis <symbol> - Get market analysis
/portfolio - View your portfolio
/signals <symbol> - Get trading signals
            """
            await update.message.reply_text(help_text)
        except Exception as e:
            logger.error(f"Error handling help command: {str(e)}")

    async def _handle_analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /analysis command"""
        try:
            if not context.args:
                await update.message.reply_text("Usage: /analysis <symbol>\nExample: /analysis BTC/USDT")
                return

            symbol = context.args[0].upper()
            analysis = await market_analyzer.get_market_analysis(symbol)

            message = (
                f"📊 Analysis for {symbol}:\n\n"
                f"Price: ${analysis['current_price']:,.2f}\n"
                f"24h Change: {analysis['price_change_24h']:+.2f}%\n"
                f"Volatility: {analysis['volatility']*100:.2f}%\n"
            )
            await update.message.reply_text(message)
        except Exception as e:
            logger.error(f"Error handling analysis command: {str(e)}")

    async def _handle_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /portfolio command"""
        try:
            user_id = update.effective_user.id
            portfolio = await portfolio_service.get_portfolio_summary(user_id)

            message = (
                f"📈 Portfolio Summary:\n\n"
                f"Total Value: ${portfolio['total_value']:,.2f}\n"
                f"Total P/L: ${portfolio['total_pnl']:+,.2f}\n"
                f"Active Positions: {portfolio['active_positions']}"
            )
            await update.message.reply_text(message)
        except Exception as e:
            logger.error(f"Error handling portfolio command: {str(e)}")

    async def _handle_signals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /signals command"""
        try:
            if not context.args:
                await update.message.reply_text("Usage: /signals <symbol>\nExample: /signals BTC/USDT")
                return

            symbol = context.args[0].upper()
            signals = await market_analyzer.get_trading_signal(symbol)

            message = (
                f"🎯 Trading Signals for {symbol}:\n\n"
                f"Current Price: ${signals['current_price']:,.2f}\n"
                f"Signal: {signals['signal']}\n"
                f"Strength: {signals['strength']}"
            )
            await update.message.reply_text(message)
        except Exception as e:
            logger.error(f"Error handling signals command: {str(e)}")

telegram_service = TelegramService()
