# 🔧 Troubleshooting Guide: "Using offline data - API connection unavailable"

## 🎯 Quick Fix Steps

### Step 1: Check Backend Status

```powershell
# Test if backend is running
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/live/health" -Method GET
```

**Expected Response**: Status 200 with JSON containing `"binance_connection": true`

### Step 2: Start Frontend with Environment Variables

**Option A: PowerShell Script (Recommended for Windows)**

```powershell
cd frontent
npm run dev:live-ps
```

**Option B: Manual Environment Setup**

```powershell
cd frontent
$env:VITE_API_URL="http://localhost:8000/api/v1"
$env:VITE_DEV_MODE="true"
npm run dev
```

**Option C: CommonJS Script**

```powershell
cd frontent
npm run dev:live-cjs
```

### Step 3: Verify Browser Console

1. Open browser to `http://localhost:5173`
2. Press F12 to open Developer Tools
3. Check Console tab for:
   - `🔧 API Service Configuration:` logs
   - `🌐 Fetching:` logs
   - Any error messages

## 🔍 Detailed Diagnostics

### Backend Diagnostics

1. **Check if backend is running:**

   ```powershell
   netstat -an | findstr :8000
   ```

2. **Test all API endpoints:**

   ```powershell
   # Health check
   Invoke-WebRequest -Uri "http://localhost:8000/api/v1/live/health"

   # Tokens
   Invoke-WebRequest -Uri "http://localhost:8000/api/v1/live/tokens"

   # Signals
   Invoke-WebRequest -Uri "http://localhost:8000/api/v1/live/signals"
   ```

3. **Check backend logs:**
   Look for any errors in your backend console output.

### Frontend Diagnostics

1. **Check if frontend is running:**

   ```powershell
   netstat -an | findstr :5173
   ```

2. **Verify environment variables:**
   Open browser console and look for:

   ```
   🔧 API Service Configuration:
   - VITE_API_URL: http://localhost:8000/api/v1
   - API_BASE_URL: http://localhost:8000/api/v1
   - LIVE_API_URL: http://localhost:8000/api/v1/live
   ```

3. **Check network requests:**
   - Open F12 Developer Tools
   - Go to Network tab
   - Refresh page
   - Look for requests to `localhost:8000`

## 🚨 Common Issues & Solutions

### Issue 1: Environment Variable Not Set

**Symptoms:** Console shows `VITE_API_URL: undefined`

**Solution:**

```powershell
# Set environment variable before starting
$env:VITE_API_URL="http://localhost:8000/api/v1"
npm run dev
```

### Issue 2: CORS Error

**Symptoms:** Console shows CORS policy error

**Solution:** Check backend CORS configuration in `backend/app/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Should allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Issue 3: Backend Not Running

**Symptoms:** Connection refused error

**Solution:**

```powershell
cd backend
python run.py
```

### Issue 4: Wrong Port

**Symptoms:** API calls fail with 404

**Solution:** Verify backend is running on port 8000:

```powershell
netstat -an | findstr :8000
```

### Issue 5: Firewall/Antivirus Blocking

**Symptoms:** Requests timeout

**Solution:**

- Temporarily disable firewall/antivirus
- Add exceptions for localhost ports 8000 and 5173

## 🔧 Manual Testing

### Test API from Node.js

```javascript
// Run: node test-api.js
const fetch = require("node-fetch");

async function test() {
  try {
    const response = await fetch("http://localhost:8000/api/v1/live/health");
    const data = await response.json();
    console.log("✅ API Working:", data);
  } catch (error) {
    console.error("❌ API Failed:", error.message);
  }
}

test();
```

### Test API from Browser

1. Open `http://localhost:5173/test-browser.html`
2. Click "Test API Connection"
3. Check results

## 📊 Expected Behavior

When working correctly, you should see:

1. **Browser Console:**

   ```
   🔧 API Service Configuration:
   - VITE_API_URL: http://localhost:8000/api/v1
   🌐 Fetching: http://localhost:8000/api/v1/live/health
   ✅ Success: http://localhost:8000/api/v1/live/health
   🌐 Fetching: http://localhost:8000/api/v1/live/tokens
   ✅ Success: http://localhost:8000/api/v1/live/tokens
   ```

2. **Frontend UI:**
   - Green banner: "Live data connected"
   - Market summary cards with real data
   - Token cards showing live prices
   - Real-time updates every 30 seconds

## 🆘 Still Not Working?

### Debug Checklist

- [ ] Backend running on port 8000
- [ ] Frontend running on port 5173
- [ ] Environment variable `VITE_API_URL` set correctly
- [ ] No CORS errors in browser console
- [ ] No firewall blocking connections
- [ ] API endpoints returning data manually

### Get Help

1. Check browser console for errors
2. Check backend console for errors
3. Test API endpoints manually
4. Verify network connectivity
5. Check Windows firewall settings

### Emergency Fallback

If live API still doesn't work, the app will automatically use mock data and show:

- Yellow banner: "Using offline data - API connection unavailable"
- Mock cryptocurrency data
- Simulated price movements

This ensures the app remains functional while you troubleshoot the API connection.
