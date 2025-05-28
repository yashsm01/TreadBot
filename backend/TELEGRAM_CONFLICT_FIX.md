# Telegram Bot Conflict Fix Guide

## Problem

You're seeing this error in your logs:

```
telegram.error.Conflict: Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
```

## What This Means

This error occurs when multiple instances of your Telegram bot are trying to get updates from Telegram's servers simultaneously. Telegram only allows one active polling connection per bot token.

## Quick Fix

### Step 1: Stop All Running Instances

1. **Stop your current application** (Ctrl+C in the terminal)
2. **Check for other running instances**:
   - Look for other terminal windows running your app
   - Check if you have multiple IDEs running the same project
   - On Windows, check Task Manager for python.exe processes

### Step 2: Run the Conflict Fixer

```bash
cd backend
python fix_telegram_conflict.py
```

This script will:

- Clear any existing webhooks
- Check for running processes
- Provide specific recommendations

### Step 3: Restart Your Application

```bash
# Make sure you're in the backend directory
cd backend

# Start your application
python main.py
# OR
uvicorn app.main:app --reload
```

## What We Fixed in the Code

### 1. Prevented Multiple Initializations

- Added singleton pattern with `_instance_running` flag
- Scheduler and notification services no longer try to initialize Telegram
- Only `main.py` initializes the Telegram service

### 2. Improved Error Handling

- Added webhook clearing before polling starts
- Better error messages with specific guidance
- Graceful degradation when Telegram fails

### 3. Better Polling Configuration

- Added `drop_pending_updates=True` to clear old updates
- Configured appropriate timeouts
- Added conflict detection with helpful error messages

## Prevention Tips

1. **Only run one instance** of your application at a time
2. **Use the singleton pattern** - don't create multiple TelegramService instances
3. **Check logs** for "Telegram bot initialized successfully" message
4. **Stop cleanly** - use Ctrl+C instead of killing processes

## Troubleshooting

### Still Getting Conflicts?

1. **Check all running Python processes**:

   ```bash
   # On Windows
   tasklist | findstr python

   # On Linux/Mac
   ps aux | grep python
   ```

2. **Kill any conflicting processes**:

   ```bash
   # Replace PID with the actual process ID
   kill <PID>
   ```

3. **Wait a few seconds** before restarting your application

### Bot Not Responding?

1. **Check your bot token** in `.env` file
2. **Verify bot permissions** with @BotFather on Telegram
3. **Check network connectivity**

### No Notifications Being Sent?

1. **Start a conversation** with your bot on Telegram
2. **Send `/start` command** to register yourself
3. **Check logs** for "Message sent to X/Y active users"

## Configuration Check

Your `.env` should have:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

## Support

If you're still having issues:

1. Check the application logs for detailed error messages
2. Run the health check: `curl http://localhost:8000/health`
3. Verify your 1inch integration is working: `python test_1inch_integration.py`

The system is designed to work even if Telegram fails, so your trading functionality should continue working regardless of Telegram issues.
