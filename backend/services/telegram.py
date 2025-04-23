import logging
import aiohttp
from typing import Dict, Optional, Tuple
import os
from dotenv import load_dotenv
from ..analysis.market_analyzer import MarketAnalyzer
from ..trader.ccxt_utils import ExchangeManager
import asyncio
from datetime import datetime, timedelta
import json
import re

logger = logging.getLogger(__name__)

# Command states
SETUP_SYMBOL, SETUP_TIMEFRAME, SETUP_AMOUNT = range(3)

class TelegramService:
    def __init__(self):
        load_dotenv()
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.session = None
        self.market_analyzer = None
        self.exchange_manager = None
        self.user_settings = {}  # Store user settings
        self.user_trades = {}    # Store user trade info
        self.user_states = {}    # Store user conversation states
        self.notification_tasks = {}  # Store notification tasks
        self._polling_task = None

    async def initialize(self, market_analyzer: MarketAnalyzer, exchange_manager: ExchangeManager):
        """Initialize the Telegram bot with required dependencies"""
        try:
            self.market_analyzer = market_analyzer
            self.exchange_manager = exchange_manager

            if not self.bot_token:
                logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
                return

            # Create aiohttp session
            self.session = aiohttp.ClientSession()

            # Test the connection
            me = await self._make_request("getMe")
            if me and me.get("ok"):
                logger.info(f"Connected to Telegram as {me.get('result', {}).get('username')}")
            else:
                logger.error("Failed to connect to Telegram")
                return

            # Start polling in background
            self._polling_task = asyncio.create_task(self._start_polling())
            logger.info("Telegram bot started successfully")

        except Exception as e:
            logger.error(f"Error initializing Telegram bot: {str(e)}")
            raise

    async def stop(self):
        """Stop the Telegram bot"""
        try:
            # Cancel polling task
            if self._polling_task:
                self._polling_task.cancel()
                try:
                    await self._polling_task
                except asyncio.CancelledError:
                    pass

            # Close session
            if self.session:
                await self.session.close()

            # Cancel all notification tasks
            for task in self.notification_tasks.values():
                task.cancel()

            self.notification_tasks.clear()

        except Exception as e:
            logger.error(f"Error stopping Telegram bot: {str(e)}")

    async def _make_request(self, method: str, params: Optional[Dict] = None) -> Dict:
        """Make a request to the Telegram Bot API"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        url = f"{self.base_url}/{method}"
        try:
            async with self.session.post(url, json=params) if params else self.session.get(url) as response:
                return await response.json()
        except Exception as e:
            logger.error(f"Error making request to Telegram API: {str(e)}")
            return {}

    async def _start_polling(self):
        """Start polling for updates"""
        offset = 0
        while True:
            try:
                updates = await self._make_request("getUpdates", {
                    "offset": offset,
                    "timeout": 30
                })

                if updates.get("ok") and updates.get("result"):
                    for update in updates["result"]:
                        offset = update["update_id"] + 1
                        await self._handle_update(update)

            except asyncio.CancelledError:
                logger.info("Polling task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in polling loop: {str(e)}")
                await asyncio.sleep(5)

    async def _handle_update(self, update: Dict):
        """Handle incoming updates"""
        try:
            if "message" in update:
                message = update["message"]
                if "text" in message:
                    text = message["text"]
                    chat_id = message["chat"]["id"]
                    user_id = str(message["from"]["id"])

                    if text.startswith("/"):
                        command = text.split()[0].lower()
                        if command == "/start":
                            await self._handle_start(chat_id, user_id)
                        elif command == "/help":
                            await self._send_help_message(chat_id)
                        elif command == "/stop":
                            await self._handle_stop(chat_id, user_id)
                        elif command == "/update":
                            await self._handle_update_command(chat_id, user_id, text)
                        elif command == "/status":
                            await self._handle_status(chat_id, user_id)
                    else:
                        # Handle user input based on state
                        await self._handle_user_input(chat_id, user_id, text)

        except Exception as e:
            logger.error(f"Error handling update: {str(e)}")

    async def _handle_start(self, chat_id: int, user_id: str):
        """Handle /start command"""
        self.user_states[user_id] = SETUP_SYMBOL
        welcome_text = (
            "Welcome to Straddle Strategy Crypto Bot 📈🤖\n\n"
            "Let's set up your trading configuration.\n\n"
            "Which crypto do you want to monitor?\n"
            f"Supported pairs: {', '.join(self.market_analyzer.supported_pairs)}\n"
            "Example: BTC/USDT"
        )
        await self._make_request("sendMessage", {
            "chat_id": chat_id,
            "text": welcome_text
        })

    async def _handle_user_input(self, chat_id: int, user_id: str, text: str):
        """Handle user input based on current state"""
        current_state = self.user_states.get(user_id)

        if current_state == SETUP_SYMBOL:
            await self._handle_symbol_input(chat_id, user_id, text)
        elif current_state == SETUP_TIMEFRAME:
            await self._handle_timeframe_input(chat_id, user_id, text)
        elif current_state == SETUP_AMOUNT:
            await self._handle_amount_input(chat_id, user_id, text)

    async def _handle_symbol_input(self, chat_id: int, user_id: str, symbol: str):
        """Handle symbol input"""
        symbol = symbol.upper()
        supported_pairs = self.market_analyzer.crypto_service.get_all_active_pairs()

        if symbol not in supported_pairs:
            await self._make_request("sendMessage", {
                "chat_id": chat_id,
                "text": f"❌ Invalid trading pair. Supported pairs: {', '.join(supported_pairs)}\nPlease try again:"
            })
            return

        self.user_settings[user_id] = {'symbol': symbol}
        self.user_states[user_id] = SETUP_TIMEFRAME

        await self._make_request("sendMessage", {
            "chat_id": chat_id,
            "text": "What's your time duration?\nAvailable options: 5m, 10m, 15m"
        })

    async def _handle_timeframe_input(self, chat_id: int, user_id: str, timeframe: str):
        """Handle timeframe input"""
        timeframe = timeframe.lower()
        if timeframe not in self.market_analyzer.timeframes:
            await self._make_request("sendMessage", {
                "chat_id": chat_id,
                "text": "❌ Invalid timeframe. Please enter: 5m, 10m, or 15m"
            })
            return

        self.user_settings[user_id]['timeframe'] = timeframe
        self.user_states[user_id] = SETUP_AMOUNT

        await self._make_request("sendMessage", {
            "chat_id": chat_id,
            "text": "How much are you investing (USDT)?\nExample: 1000"
        })

    async def _handle_amount_input(self, chat_id: int, user_id: str, amount: str):
        """Handle amount input"""
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError("Amount must be positive")

            self.user_settings[user_id]['amount'] = amount
            del self.user_states[user_id]  # Clear setup state

            # Initialize trade tracking
            self.user_trades[user_id] = {
                'last_action': None,
                'entry_price': None,
                'quantity': None,
                'timestamp': None
            }

            # Start notifications
            await self._start_user_notifications(chat_id, user_id)

            # Send confirmation
            settings = self.user_settings[user_id]
            await self._make_request("sendMessage", {
                "chat_id": chat_id,
                "text": (
                    "✅ Setup complete!\n\n"
                    f"🔹 Crypto: {settings['symbol']}\n"
                    f"🕒 Timeframe: {settings['timeframe']}\n"
                    f"💰 Investment: {settings['amount']} USDT\n\n"
                    "You will receive regular updates with trading signals.\n\n"
                    "Commands:\n"
                    "/update - Update trade (e.g., /update buy 63500 0.0015)\n"
                    "/stop - Stop notifications\n"
                    "/help - Show help message"
                )
            })

        except ValueError:
            await self._make_request("sendMessage", {
                "chat_id": chat_id,
                "text": "❌ Invalid amount. Please enter a positive number:"
            })

    async def _handle_update_command(self, chat_id: int, user_id: str, text: str):
        """Handle /update command"""
        try:
            # Parse command: /update action price qty
            parts = text.split()
            if len(parts) != 4:
                raise ValueError("Invalid format. Use: /update action price qty")

            action = parts[1].lower()
            if action not in ['buy', 'sell']:
                raise ValueError("Action must be 'buy' or 'sell'")

            price = float(parts[2])
            quantity = float(parts[3])

            if price <= 0 or quantity <= 0:
                raise ValueError("Price and quantity must be positive")

            # Update trade info
            self.user_trades[user_id] = {
                'last_action': action,
                'entry_price': price,
                'quantity': quantity,
                'timestamp': datetime.now().isoformat()
            }

            # Send confirmation
            await self._make_request("sendMessage", {
                "chat_id": chat_id,
                "text": (
                    "✅ Trade updated successfully!\n\n"
                    f"Action: {action.upper()}\n"
                    f"Price: ${price:,.2f}\n"
                    f"Quantity: {quantity}\n"
                    f"Total: ${price * quantity:,.2f}"
                )
            })

        except (ValueError, IndexError) as e:
            await self._make_request("sendMessage", {
                "chat_id": chat_id,
                "text": f"❌ Error: {str(e)}\nFormat: /update buy|sell price quantity\nExample: /update buy 63500 0.0015"
            })

    async def _start_user_notifications(self, chat_id: int, user_id: str):
        """Start notifications for a user"""
        if user_id in self.notification_tasks:
            self.notification_tasks[user_id].cancel()

        settings = self.user_settings[user_id]
        interval_minutes = int(settings['timeframe'].replace('m', ''))

        async def send_periodic_updates():
            while True:
                try:
                    # Get market analysis
                    analysis = await self.market_analyzer.get_market_analysis(
                        settings['symbol'],
                        settings['timeframe']
                    )

                    # Get trade info
                    trade_info = self.user_trades.get(user_id, {})
                    current_price = analysis['current_price']

                    # Calculate P&L if we have trade info
                    pnl_text = ""
                    if trade_info.get('entry_price') and trade_info.get('quantity'):
                        entry_total = trade_info['entry_price'] * trade_info['quantity']
                        current_total = current_price * trade_info['quantity']
                        pnl = current_total - entry_total
                        pnl_text = (
                            f"📦 Qty: {trade_info['quantity']} {settings['symbol'].split('/')[0]}\n"
                            f"📊 P&L: ${pnl:+,.2f} "
                            f"({'✅' if pnl > 0 else '❌'})\n"
                        )

                    # Format message
                    message = (
                        "📢 STRADDLE STRATEGY SIGNAL\n\n"
                        f"🔹 Crypto: {settings['symbol']}\n"
                        f"🕒 Timeframe: {settings['timeframe']}\n"
                    )

                    if trade_info.get('last_action'):
                        message += (
                            f"💰 Last Action: {trade_info['last_action'].upper()}\n"
                            f"📈 Entry Price: ${trade_info['entry_price']:,.2f}\n"
                        )

                    message += (
                        f"📉 Current Price: ${current_price:,.2f}\n"
                        f"{pnl_text}\n"
                        f"🧠 Signal: {analysis['recommendation']['action'].upper()}\n"
                        f"🎯 Reason: {analysis['recommendation']['reason']}\n"
                    )

                    if analysis['recommendation'].get('stop_loss'):
                        message += f"🛑 Stop Loss: ${analysis['recommendation']['stop_loss']:,.2f}\n"
                    if analysis['recommendation'].get('target_price'):
                        message += f"🎯 Target: ${analysis['recommendation']['target_price']:,.2f}\n"

                    message += f"\n📬 Next update in {interval_minutes} minutes..."

                    # Add TradingView chart link
                    tv_symbol = settings['symbol'].replace('/', '')
                    message += f"\n\n📊 Chart: https://www.tradingview.com/chart/?symbol={tv_symbol}"

                    await self._make_request("sendMessage", {
                        "chat_id": chat_id,
                        "text": message,
                        "disable_web_page_preview": True
                    })

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error sending update to user {user_id}: {str(e)}")

                await asyncio.sleep(interval_minutes * 60)

        self.notification_tasks[user_id] = asyncio.create_task(send_periodic_updates())

    async def _handle_stop(self, chat_id: int, user_id: str):
        """Handle /stop command"""
        if user_id in self.notification_tasks:
            self.notification_tasks[user_id].cancel()
            del self.notification_tasks[user_id]
            if user_id in self.user_settings:
                del self.user_settings[user_id]
            if user_id in self.user_trades:
                del self.user_trades[user_id]
            if user_id in self.user_states:
                del self.user_states[user_id]

            await self._make_request("sendMessage", {
                "chat_id": chat_id,
                "text": "✅ Monitoring stopped. Use /start to begin again."
            })
        else:
            await self._make_request("sendMessage", {
                "chat_id": chat_id,
                "text": "No active monitoring to stop."
            })

    async def _handle_status(self, chat_id: int, user_id: str):
        """Handle /status command - show current trading status"""
        try:
            # Check if user has active monitoring
            if user_id not in self.user_settings:
                await self._make_request("sendMessage", {
                    "chat_id": chat_id,
                    "text": "❌ No active monitoring. Use /start to begin monitoring a crypto pair."
                })
                return

            settings = self.user_settings[user_id]
            trade_info = self.user_trades.get(user_id, {})

            # Get current market analysis
            analysis = await self.market_analyzer.get_market_analysis(
                settings['symbol'],
                settings['timeframe']
            )

            current_price = analysis['current_price']

            # Calculate P&L if we have trade info
            pnl_text = ""
            if trade_info.get('entry_price') and trade_info.get('quantity'):
                entry_total = trade_info['entry_price'] * trade_info['quantity']
                current_total = current_price * trade_info['quantity']
                pnl = current_total - entry_total
                pnl_percent = (pnl / entry_total) * 100
                pnl_text = (
                    f"📦 Quantity: {trade_info['quantity']} {settings['symbol'].split('/')[0]}\n"
                    f"📊 P&L: ${pnl:+,.2f} ({pnl_percent:+.2f}%) "
                    f"({'✅' if pnl > 0 else '❌'})\n"
                )

            # Get time until next update
            next_update = ""
            if user_id in self.notification_tasks:
                interval_minutes = int(settings['timeframe'].replace('m', ''))
                next_update = f"\n⏰ Next scheduled update in {interval_minutes} minutes"

            # Format status message
            status = (
                "📈 CURRENT STATUS\n\n"
                f"🔹 Trading Pair: {settings['symbol']}\n"
                f"🕒 Timeframe: {settings['timeframe']}\n"
                f"💰 Investment: {settings['amount']} USDT\n"
            )

            if trade_info.get('last_action'):
                time_str = datetime.fromisoformat(trade_info['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
                status += (
                    f"\n💫 Last Trade:\n"
                    f"📅 Time: {time_str}\n"
                    f"🎯 Action: {trade_info['last_action'].upper()}\n"
                    f"💵 Entry Price: ${trade_info['entry_price']:,.2f}\n"
                )

            status += (
                f"\n📊 Current Status:\n"
                f"💰 Current Price: ${current_price:,.2f}\n"
                f"{pnl_text}\n"
                f"📈 Signal: {analysis['recommendation']['action'].upper()}\n"
                f"💭 Reason: {analysis['recommendation']['reason']}\n"
            )

            if analysis['recommendation'].get('stop_loss'):
                status += f"🛑 Stop Loss: ${analysis['recommendation']['stop_loss']:,.2f}\n"
            if analysis['recommendation'].get('target_price'):
                status += f"🎯 Target: ${analysis['recommendation']['target_price']:,.2f}\n"

            status += next_update

            # Add TradingView chart link
            tv_symbol = settings['symbol'].replace('/', '')
            status += f"\n\n📊 Chart: https://www.tradingview.com/chart/?symbol={tv_symbol}"

            await self._make_request("sendMessage", {
                "chat_id": chat_id,
                "text": status,
                "disable_web_page_preview": True
            })

        except Exception as e:
            logger.error(f"Error getting status: {str(e)}")
            await self._make_request("sendMessage", {
                "chat_id": chat_id,
                "text": f"❌ Error getting status: {str(e)}"
            })

    async def _send_help_message(self, chat_id: int):
        """Send help message"""
        help_text = (
            "🤖 Available Commands:\n\n"
            "/start - Start monitoring a crypto pair\n"
            "/status - Check current trading status\n"
            "/update - Update trade details\n"
            "  Format: /update action price qty\n"
            "  Example: /update buy 63500 0.0015\n"
            "/stop - Stop monitoring\n"
            "/help - Show this help message\n\n"
            "📊 Features:\n"
            "• Real-time price monitoring\n"
            "• Straddle strategy signals\n"
            "• P&L tracking\n"
            "• Auto trade suggestions\n"
            "• TradingView chart links"
        )
        await self._make_request("sendMessage", {
            "chat_id": chat_id,
            "text": help_text
        })

    async def send_error_notification(self, error_message: str, details: Optional[Dict] = None):
        """Send error notification"""
        if not self.chat_id:
            logger.error("TELEGRAM_CHAT_ID not found in environment variables")
            return

        message = f"❌ Error: {error_message}"
        if details:
            message += "\n\nDetails:"
            for key, value in details.items():
                message += f"\n{key}: {value}"

        await self._make_request("sendMessage", {
            "chat_id": self.chat_id,
            "text": message
        })

    async def send_test_notification(self) -> bool:
        """Send a test notification"""
        if not self.chat_id:
            logger.error("TELEGRAM_CHAT_ID not found in environment variables")
            return False

        try:
            result = await self._make_request("sendMessage", {
                "chat_id": self.chat_id,
                "text": "✅ Telegram bot is working correctly!"
            })
            return result.get("ok", False)
        except Exception as e:
            logger.error(f"Error sending test notification: {str(e)}")
            return False
