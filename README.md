# 🚀 Time-Based Straddling Strategy

> **Advanced Cryptocurrency Trading Bot with Time-Based Straddling Strategy**

[![YouTube Video](https://img.shields.io/badge/YouTube-Video%20Tutorial-red?style=for-the-badge&logo=youtube)](https://youtu.be/ymGSRTswBFU?si=WPFF6jPTAeRMxkec)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3%2B-61DAFB?style=for-the-badge&logo=react)](https://reactjs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5%2B-3178C6?style=for-the-badge&logo=typescript)](https://typescriptlang.org)

## 📖 Overview

The Time-Based Straddling Strategy is a sophisticated cryptocurrency trading system that employs advanced algorithmic trading techniques to capture market volatility through strategic position placement. The system utilizes multiple timeframes and dynamic volatility analysis to optimize entry and exit points.

### 🎯 Key Features

- **🔄 Automated Straddle Trading**: Executes both long and short positions simultaneously
- **⏰ Multi-Timeframe Analysis**: Short (5m), Medium (1h), and Long (4h) timeframe strategies
- **📊 Dynamic Volatility Calculation**: Adaptive entry levels based on real-time market conditions
- **🎛️ Smart Position Management**: Intelligent TP/SL calculation with 1:3 buy/sell ratios
- **📱 Telegram Integration**: Real-time notifications and trading updates
- **🔄 Auto-Swap Functionality**: Automatic conversion between crypto and stablecoins
- **📈 Portfolio Management**: Comprehensive portfolio tracking and analysis
- **🖥️ Modern Web Interface**: Real-time dashboard with live market data
- **🔐 Paper Trading Mode**: Safe testing environment before live trading

## 🏗️ Architecture

```
Time-Based Straddling Strategy/
├── backend/                    # FastAPI Backend
│   ├── app/                   # Main application
│   │   ├── api/v1/           # API routes
│   │   ├── models/           # Database models
│   │   ├── services/         # Business logic
│   │   ├── crud/             # Database operations
│   │   └── core/             # Configuration & database
│   ├── alembic/              # Database migrations
│   └── scripts/              # Utility scripts
├── frontent/ [sic]           # React/TypeScript Frontend
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── services/         # API services
│   │   ├── hooks/            # Custom React hooks
│   │   └── types/            # TypeScript definitions
│   └── ...
└── crypto_scheduler/         # Background job scheduler
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+**
- **Node.js 16+**
- **PostgreSQL 12+**
- **Git**

### 1. Clone the Repository

```bash
git clone <repository-url>
cd "Time-Based Straddling Strategy"
```

### 2. Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration
```

### 3. Database Setup

```bash
# Create PostgreSQL database
createdb crypto_trading

# Run migrations
alembic upgrade head

# Optional: Sync crypto data
python scripts/sync_crypto.py
```

### 4. Frontend Setup

```bash
# Navigate to frontend
cd frontent

# Install dependencies
npm install

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration
```

### 5. Start the Application

**Backend:**

```bash
cd backend
python run.py
```

**Frontend:**

```bash
cd frontent
npm run dev
```

**Scheduler (Optional):**

```bash
cd backend/crypto_scheduler
python start.py
```

## ⚙️ Configuration

### Backend Configuration (`backend/.env`)

```env
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=crypto_trading

# Trading Settings
PAPER_TRADING=true
STRATEGY=SHORT  # SHORT, MEDIUM, LONG
DEFAULT_TRADING_PAIR=BTC/USDT

# Exchange API Keys
BINANCE_API_KEY=your_binance_api_key
BINANCE_SECRET_KEY=your_binance_secret_key

# Telegram (Optional)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# 1inch API (For Swaps)
ONEINCH_API_KEY=your_oneinch_api_key
WALLET_ADDRESS=your_wallet_address
PRIVATE_KEY=your_private_key
```

### Frontend Configuration (`frontent/.env`)

```env
VITE_API_URL=http://localhost:8000/api/v1
VITE_DEV_MODE=true
VITE_AUTO_REFRESH_INTERVAL=30000
VITE_ENABLE_MOCK_FALLBACK=true
```

## 🎯 Trading Strategy

### Straddle Strategy Logic

The Time-Based Straddling Strategy implements a sophisticated approach to cryptocurrency trading:

1. **Volatility Analysis**: Calculates volatility across multiple timeframes
2. **Dynamic Entry Levels**: Adjusts entry points based on market conditions
3. **Risk Management**: Implements 1:3 buy/sell ratios with intelligent stop-loss
4. **Auto-Rebalancing**: Automatically closes and reopens positions based on profit targets

### Strategy Parameters

| Parameter          | Short Strategy | Medium Strategy | Long Strategy |
| ------------------ | -------------- | --------------- | ------------- |
| **Timeframe**      | 5 minutes      | 1 hour          | 4 hours       |
| **Take Profit**    | 0.8%           | 3.0%            | 6.0%          |
| **Stop Loss**      | 0.5%           | 2.0%            | 4.0%          |
| **Buy:Sell Ratio** | 1:3            | 1:3             | 1:3           |

## 📊 API Endpoints

### Live Trading Data

- `GET /api/v1/live/health` - System health check
- `GET /api/v1/live/tokens` - Real-time token prices
- `GET /api/v1/live/signals` - Trading signals
- `GET /api/v1/live/market-overview` - Market summary

### Trading Operations

- `POST /api/v1/straddle/create` - Create straddle position
- `GET /api/v1/straddle/status/{symbol}` - Get position status
- `POST /api/v1/straddle/close/{symbol}` - Close position

### Portfolio Management

- `GET /api/v1/portfolio/summary` - Portfolio overview
- `GET /api/v1/portfolio/history` - Trading history
- `GET /api/v1/portfolio/performance` - Performance metrics

## 🔧 Advanced Features

### Auto-Swap Functionality

The system can automatically swap between cryptocurrencies and stablecoins based on:

- Market trend analysis
- Profit thresholds
- Risk management rules
- Intraday pattern recognition

### Multi-Exchange Support

- **Binance**: Primary exchange for trading
- **1inch**: DEX aggregator for optimal swap rates
- **Extensible**: Easy to add new exchange integrations

### Telegram Bot Integration

Get real-time notifications for:

- Trade executions
- Profit/Loss updates
- System alerts
- Market opportunities

## 📈 Performance Monitoring

### Built-in Analytics

- **Real-time P&L tracking**
- **Win/loss ratios**
- **Drawdown analysis**
- **Performance attribution**
- **Risk metrics**

### Logging and Monitoring

- Comprehensive logging system
- Health check endpoints
- Performance metrics collection
- Error tracking and alerting

## 🧪 Testing

### Run Backend Tests

```bash
cd backend
pytest app/tests/ -v
```

### Test API Connectivity

```bash
# Test environment setup
node frontent/test-env.js

# Test API service
node frontent/test-api-service.js
```

## 🔒 Security

### Best Practices Implemented

- **API Key Management**: Secure storage of exchange credentials
- **Paper Trading Mode**: Safe testing environment
- **Input Validation**: Comprehensive parameter validation
- **Rate Limiting**: Protection against API abuse
- **Secure Communications**: HTTPS and encrypted connections

### Wallet Security

- Private keys are encrypted and never logged
- Multi-signature support ready
- Hardware wallet integration possible

## 📚 Documentation

### Additional Resources

- 📖 [API Setup Guide](LIVE_API_SETUP.md)
- 🚀 [Frontend Setup Guide](START_FRONTEND.md)
- 🔧 [Troubleshooting Guide](TROUBLESHOOTING.md)
- 📺 [Video Tutorial](https://youtu.be/ymGSRTswBFU?si=WPFF6jPTAeRMxkec)

### API Documentation

Once the backend is running, access the interactive API documentation at:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

**This software is for educational and research purposes only. Cryptocurrency trading involves substantial risk of loss and is not suitable for every investor. Past performance does not guarantee future results. Always conduct your own research and consider consulting with a financial advisor before making investment decisions.**

## 🆘 Support

- 📺 **Video Tutorial**: [YouTube](https://youtu.be/ymGSRTswBFU?si=WPFF6jPTAeRMxkec)
- 📧 **Issues**: Create an issue on GitHub
- 💬 **Discussions**: Use GitHub Discussions for questions

## 🔗 Links

- **Repository**: [GitHub](https://github.com/your-username/time-based-straddling-strategy)
- **Documentation**: [Wiki](https://github.com/your-username/time-based-straddling-strategy/wiki)
- **Video Tutorial**: [YouTube](https://youtu.be/ymGSRTswBFU?si=WPFF6jPTAeRMxkec)

---

**⭐ If you find this project helpful, please consider giving it a star!**
