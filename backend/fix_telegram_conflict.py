#!/usr/bin/env python3
"""
Script to fix Telegram bot conflict issues
This script helps resolve the "Conflict: terminated by other getUpdates request" error
"""

import asyncio
import requests
import os
import sys
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logger import logger

async def clear_telegram_webhook():
    """Clear any existing webhook to ensure polling can work"""
    try:
        if not settings.TELEGRAM_BOT_TOKEN:
            print("❌ No Telegram bot token found in settings")
            return False

        # Clear webhook
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/deleteWebhook"
        response = requests.post(url, json={"drop_pending_updates": True})

        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                print("✅ Telegram webhook cleared successfully")
                return True
            else:
                print(f"❌ Failed to clear webhook: {result.get('description')}")
                return False
        else:
            print(f"❌ HTTP error clearing webhook: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error clearing webhook: {str(e)}")
        return False

async def get_bot_info():
    """Get bot information to verify token is working"""
    try:
        if not settings.TELEGRAM_BOT_TOKEN:
            print("❌ No Telegram bot token found in settings")
            return False

        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe"
        response = requests.get(url)

        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                bot_info = result.get("result", {})
                print(f"✅ Bot info: @{bot_info.get('username')} ({bot_info.get('first_name')})")
                return True
            else:
                print(f"❌ Failed to get bot info: {result.get('description')}")
                return False
        else:
            print(f"❌ HTTP error getting bot info: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error getting bot info: {str(e)}")
        return False

def check_running_processes():
    """Check for running Python processes that might be using the bot"""
    try:
        import psutil

        python_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and 'python' in proc.info['name'].lower():
                    cmdline = proc.info['cmdline']
                    if cmdline and any('main.py' in arg or 'uvicorn' in arg or 'fastapi' in arg for arg in cmdline):
                        python_processes.append({
                            'pid': proc.info['pid'],
                            'cmdline': ' '.join(cmdline) if cmdline else 'N/A'
                        })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if python_processes:
            print(f"\n🔍 Found {len(python_processes)} potentially related Python processes:")
            for proc in python_processes:
                print(f"   PID {proc['pid']}: {proc['cmdline']}")
            print("\n💡 Consider stopping these processes before restarting your application")
        else:
            print("✅ No conflicting Python processes found")

        return python_processes

    except ImportError:
        print("⚠️  psutil not available, cannot check for running processes")
        print("   Install with: pip install psutil")
        return []
    except Exception as e:
        print(f"❌ Error checking processes: {str(e)}")
        return []

async def main():
    """Main function to fix Telegram conflicts"""
    print("🔧 Telegram Bot Conflict Fixer")
    print("=" * 50)

    # Check bot token and get info
    print("\n1. Checking bot configuration...")
    bot_ok = await get_bot_info()

    if not bot_ok:
        print("❌ Bot configuration issue. Please check your TELEGRAM_BOT_TOKEN")
        return

    # Clear webhook
    print("\n2. Clearing any existing webhook...")
    webhook_cleared = await clear_telegram_webhook()

    # Check for running processes
    print("\n3. Checking for conflicting processes...")
    processes = check_running_processes()

    # Provide recommendations
    print("\n" + "=" * 50)
    print("📋 RECOMMENDATIONS:")
    print("=" * 50)

    if webhook_cleared:
        print("✅ Webhook cleared - polling should work now")
    else:
        print("⚠️  Webhook clearing failed - may cause issues")

    if processes:
        print("⚠️  Stop any running instances of your application before restarting")
        print("   Use Ctrl+C in the terminal or kill the processes by PID")

    print("\n🚀 NEXT STEPS:")
    print("1. Make sure no other instances of your app are running")
    print("2. Restart your FastAPI application")
    print("3. Check the logs for 'Telegram bot initialized successfully'")
    print("4. The conflict error should be resolved")

    print(f"\n💡 Your bot username: Check the bot info above")
    print(f"💡 Chat ID for testing: {settings.TELEGRAM_CHAT_ID}")

if __name__ == "__main__":
    asyncio.run(main())
