# 🚀 How to Start the Frontend with Live API

## Quick Start (Choose One Method)

### Method 1: Using Batch File (Recommended for Windows)

```cmd
cd frontent
set-env.bat
```

### Method 2: PowerShell with Environment Variables

```powershell
cd frontent
$env:VITE_API_URL="http://localhost:8000/api/v1"
$env:VITE_DEV_MODE="true"
npm run dev
```

### Method 3: Regular Start (Uses defaults from vite.config.ts)

```powershell
cd frontent
npm run dev
```

## 🔍 Debugging Steps

1. **Start the frontend** using any method above
2. **Open browser** to `http://localhost:5173`
3. **Open Developer Tools** (F12)
4. **Check Console tab** for these logs:

### Expected Console Output:

```
🔧 Environment Variables Debug:
- VITE_API_URL from env: http://localhost:8000/api/v1
- API_BASE_URL: http://localhost:8000/api/v1
- LIVE_API_URL: http://localhost:8000/api/v1/live

🚀 loadLiveData called
🏥 Starting health check...
🏥 Health check URL: http://localhost:8000/api/v1/live/health
🌐 Attempting to fetch: http://localhost:8000/api/v1/live/health
✅ Success for http://localhost:8000/api/v1/live/health
🏥 Health check result: {status: "healthy", binance_connection: true}
✅ Health check passed, setting online status
```

### If You See Issues:

- Look for `❌` error messages in console
- Check if `VITE_API_URL` is `undefined`
- Verify the API URLs being called

## 🎯 What to Look For

### ✅ Working (Green Banner):

- "Live data connected"
- Real cryptocurrency prices
- Green dot indicators

### ⚠️ Not Working (Yellow Banner):

- "Using offline data - API connection unavailable"
- Mock data being used
- Check console for error details

## 🔧 Troubleshooting

If you still see "Using offline data":

1. **Check Backend:** Make sure `python run.py` is running in backend folder
2. **Check Console:** Look for specific error messages
3. **Check Network Tab:** See if API requests are being made
4. **Try Manual Test:** Run `node test-env.js` to verify API connectivity

The extensive console logging will show you exactly where the connection is failing!
