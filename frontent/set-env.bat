@echo off
echo 🚀 Setting Environment Variables and Starting Development Server...

set VITE_API_URL=http://localhost:8000/api/v1
set VITE_DEV_MODE=true
set VITE_AUTO_REFRESH_INTERVAL=30000
set VITE_ENABLE_MOCK_FALLBACK=true

echo 📡 API URL: %VITE_API_URL%
echo 🔧 Dev Mode: %VITE_DEV_MODE%
echo 🔄 Refresh Interval: %VITE_AUTO_REFRESH_INTERVAL%ms
echo.

echo Starting Vite development server...
npm run dev
