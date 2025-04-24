# Crypto Straddle Trading Bot

An automated cryptocurrency trading system using a Time-Based Straddling Strategy.

## Features

- Automated trading on Binance exchange
- Time-based straddling strategy with configurable intervals
- Support for multiple trading pairs
- Real-time trade notifications via Telegram
- Paper trading mode for testing
- Web dashboard for monitoring and configuration
- Daily P&L summaries

## Tech Stack

- Backend: Python (FastAPI), ccxt, PostgreSQL
- Frontend: Angular 15+
- Additional: Telegram Bot API

## Setup Instructions

1. Clone the repository:

```bash
git clone https://github.com/yourusername/crypto-straddle-bot.git
cd crypto-straddle-bot
```

2. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file with the following configuration:

```env
# Database Configuration
DATABASE_URL=postgresql://postgres:1234@localhost:5432/crypto_trading

# Binance API Configuration
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Trading Configuration
DEFAULT_INTERVAL=5m
DEFAULT_BREAKOUT_PCT=0.5
DEFAULT_TP_PCT=1.0
DEFAULT_SL_PCT=0.5
DEFAULT_QUANTITY=0.001

# Paper Trading Mode (true/false)
PAPER_TRADING=true
```

5. Set up the database:

```bash
# Create PostgreSQL database
createdb crypto_trading

# Run migrations (when implemented)
alembic upgrade head
```

6. Start the backend server:

```bash
cd backend
uvicorn main:app --reload
```

7. Start the frontend development server:

```bash
cd frontend
ng serve
```

## API Endpoints

- `GET /trades`: List all trades
- `GET /trades/profit-summary`: Get daily/monthly profit/loss summary
- `GET /config`: Fetch current strategy configuration
- `POST /config/update`: Update strategy configuration
- `POST /trade/manual`: Trigger manual straddle trade
- `GET /status`: Health check endpoint

## Trading Strategy

The bot implements a time-based straddling strategy:

1. At configurable intervals (5min, 15min, 1hr):
   - Fetches current market price
   - Places BUY order at (price + breakout%)
   - Places SELL order at (price - breakout%)
2. When one order executes:
   - Cancels the other order
   - Sets up Take Profit and Stop Loss orders
3. Tracks trades and manages positions

## Security Considerations

- Never commit your `.env` file
- Use paper trading mode for testing
- Start with small position sizes
- Monitor the bot regularly
- Keep your API keys secure

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License - see LICENSE file for details
