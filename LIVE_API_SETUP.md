# 🚀 Live API Integration Setup Guide

This guide will help you set up and run the frontend with live data from your backend API.

## 📋 Prerequisites

1. **Backend API Running**: Ensure your FastAPI backend is running on `http://localhost:8000`
2. **Node.js**: Version 16+ installed
3. **Dependencies**: All npm packages installed in the frontend

## 🔧 Setup Instructions

### 1. Start the Backend API

First, make sure your backend is running with the live routes:

```bash
# Navigate to backend directory
cd backend

# Start the FastAPI server
python run.py
```

The backend should be accessible at: `http://localhost:8000`

### 2. Verify API Endpoints

Test that your live API endpoints are working:

```bash
# Test health check
curl http://localhost:8000/api/v1/live/health

# Test tokens endpoint
curl http://localhost:8000/api/v1/live/tokens

# Test signals endpoint
curl http://localhost:8000/api/v1/live/signals
```

### 3. Start the Frontend

Navigate to the frontend directory and start the development server:

```bash
# Navigate to frontend directory
cd frontent

# Install dependencies (if not already done)
npm install

# Option 1: Start with live API integration (ES Module)
npm run dev:live

# Option 2: Start with live API integration (CommonJS - if ES module fails)
npm run dev:live-cjs

# Option 3: Windows batch file
start-dev.bat

# Option 4: Start normally (will use default API URL)
npm run dev
```

**Note**: If you encounter ES module errors, use the CommonJS version (`npm run dev:live-cjs`) or the batch file on Windows.

## 🌐 Environment Configuration

### Manual Environment Setup

Create a `.env` file in the `frontent` directory:

```env
VITE_API_URL=http://localhost:8000/api/v1
VITE_DEV_MODE=true
VITE_AUTO_REFRESH_INTERVAL=30000
VITE_ENABLE_MOCK_FALLBACK=true
VITE_HEALTH_CHECK_INTERVAL=60000
```

### Available Environment Variables

| Variable                     | Default                        | Description                      |
| ---------------------------- | ------------------------------ | -------------------------------- |
| `VITE_API_URL`               | `http://localhost:8000/api/v1` | Backend API base URL             |
| `VITE_DEV_MODE`              | `true`                         | Enable development mode features |
| `VITE_AUTO_REFRESH_INTERVAL` | `30000`                        | Auto-refresh interval (ms)       |
| `VITE_ENABLE_MOCK_FALLBACK`  | `true`                         | Use mock data if API fails       |
| `VITE_HEALTH_CHECK_INTERVAL` | `60000`                        | Health check interval (ms)       |

## 📊 Features

### Live Data Integration

- **Real-time Token Prices**: Updates every 30 seconds
- **Trading Signals**: Generated based on market analysis
- **Market Overview**: Summary statistics and trends
- **Connection Status**: Visual indicators for API connectivity
- **Fallback Mode**: Uses mock data when API is unavailable

### API Endpoints Used

| Endpoint                | Description           | Refresh Rate |
| ----------------------- | --------------------- | ------------ |
| `/live/tokens`          | Token prices and data | 30 seconds   |
| `/live/signals`         | Trading signals       | 2 minutes    |
| `/live/market-overview` | Market summary        | On demand    |
| `/live/health`          | API health status     | 1 minute     |
| `/live/trending`        | Trending tokens       | On demand    |

### Visual Indicators

- 🟢 **Green Dot**: Live data connected
- 🟡 **Yellow Dot**: Using offline/cached data
- 🔴 **Red Dot**: API connection failed
- ⚡ **Pulse Animation**: Real-time updates active

## 🛠️ Troubleshooting

### Common Issues

#### 1. API Connection Failed

```
Error: Failed to fetch from http://localhost:8000/api/v1/live/health
```

**Solutions:**

- Ensure backend is running on port 8000
- Check if CORS is properly configured in backend
- Verify firewall/antivirus isn't blocking connections

#### 2. No Live Data Showing

```
Using offline data - API connection unavailable
```

**Solutions:**

- Check backend logs for errors
- Verify Binance API connection in backend
- Test individual API endpoints manually

#### 3. CORS Errors

```
Access to fetch at 'http://localhost:8000' from origin 'http://localhost:5173' has been blocked by CORS policy
```

**Solutions:**

- Add frontend URL to CORS origins in backend
- Check `app/main.py` CORS configuration

### Debug Mode

Enable additional logging by setting:

```env
VITE_DEV_MODE=true
```

This will show:

- API request/response logs in browser console
- Connection status changes
- Data refresh events

## 📈 Performance Optimization

### Refresh Intervals

Adjust refresh rates based on your needs:

```env
# More frequent updates (higher API usage)
VITE_AUTO_REFRESH_INTERVAL=15000

# Less frequent updates (lower API usage)
VITE_AUTO_REFRESH_INTERVAL=60000
```

### API Caching

The frontend implements smart caching:

- Token data: 30-second cache
- Trading signals: 2-minute cache
- Market overview: On-demand only

## 🔐 Security Notes

- Never expose private keys in frontend code
- Use environment variables for sensitive configuration
- The frontend only reads public market data
- No trading operations are performed from frontend

## 📱 Mobile Responsiveness

The interface is fully responsive and includes:

- Touch-friendly token cards
- Mobile-optimized layouts
- Swipe gestures for navigation
- Adaptive font sizes

## 🚀 Production Deployment

For production deployment:

1. **Build the frontend:**

   ```bash
   npm run build
   ```

2. **Set production environment:**

   ```env
   VITE_API_URL=https://your-api-domain.com/api/v1
   VITE_DEV_MODE=false
   VITE_AUTO_REFRESH_INTERVAL=60000
   ```

3. **Deploy the `dist` folder** to your web server

## 📞 Support

If you encounter issues:

1. Check browser console for errors
2. Verify backend API is responding
3. Test API endpoints manually
4. Check network connectivity
5. Review backend logs

---

**Happy Trading! 📈**
