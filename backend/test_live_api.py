"""
Test script to demonstrate the Live API endpoints
Run this after starting the FastAPI server
"""
import requests
import json
from datetime import datetime

# Base URL for your API (adjust if needed)
BASE_URL = "http://localhost:8000/api/v1/live"

def test_live_tokens():
    """Test the live tokens endpoint"""
    print("🔍 Testing Live Tokens Endpoint...")

    try:
        # Test getting all default tokens
        response = requests.get(f"{BASE_URL}/tokens")

        if response.status_code == 200:
            tokens = response.json()
            print(f"✅ Successfully fetched {len(tokens)} tokens")

            # Display first few tokens
            for token in tokens[:3]:
                print(f"  {token['symbol']}: ${token['price']} ({token['change24h']:+.2f}%)")
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"❌ Exception: {str(e)}")

def test_specific_tokens():
    """Test getting specific tokens"""
    print("\n🔍 Testing Specific Tokens (DOGE, BTC, ETH)...")

    try:
        # Test getting specific tokens including DOGE
        response = requests.get(f"{BASE_URL}/tokens?symbols=DOGE,BTC,ETH")

        if response.status_code == 200:
            tokens = response.json()
            print(f"✅ Successfully fetched {len(tokens)} specific tokens")

            for token in tokens:
                print(f"  {token['symbol']}: ${token['price']} ({token['change24h']:+.2f}%) Vol: {token['volume']:,}")
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"❌ Exception: {str(e)}")

def test_live_signals():
    """Test the live signals endpoint"""
    print("\n🔍 Testing Live Signals Endpoint...")

    try:
        response = requests.get(f"{BASE_URL}/signals?limit=3")

        if response.status_code == 200:
            signals = response.json()
            print(f"✅ Successfully generated {len(signals)} signals")

            for signal in signals:
                print(f"  {signal['tokenId'].upper()}: {signal['type']} @ ${signal['entry']} "
                      f"(Confidence: {signal['confidence']}%)")
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"❌ Exception: {str(e)}")

def test_token_details():
    """Test getting detailed token information"""
    print("\n🔍 Testing Token Details (DOGE)...")

    try:
        response = requests.get(f"{BASE_URL}/token/DOGE")

        if response.status_code == 200:
            token = response.json()
            print(f"✅ Successfully fetched details for {token['symbol']}")
            print(f"  Price: ${token['price']}")
            print(f"  24h Change: {token['change24h']:+.2f}%")
            print(f"  24h High: ${token['high24h']}")
            print(f"  24h Low: ${token['low24h']}")
            print(f"  Volume: {token['volume']:,}")
            print(f"  Volatility: {token['volatility']:.4f}")
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"❌ Exception: {str(e)}")

def test_market_overview():
    """Test the market overview endpoint"""
    print("\n🔍 Testing Market Overview...")

    try:
        response = requests.get(f"{BASE_URL}/market-overview")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Successfully fetched market overview")

            summary = data['marketSummary']
            print(f"  Total Tokens: {summary['totalTokens']}")
            print(f"  Total Volume: ${summary['totalVolume']:,}")
            print(f"  Average 24h Change: {summary['averageChange24h']:+.2f}%")
            print(f"  Positive Performers: {summary['positivePerformers']}")
            print(f"  Active Signals: {summary['activeSignals']}")
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"❌ Exception: {str(e)}")

def test_health_check():
    """Test the health check endpoint"""
    print("\n🔍 Testing Health Check...")

    try:
        response = requests.get(f"{BASE_URL}/health")

        if response.status_code == 200:
            health = response.json()
            print(f"✅ Service Status: {health['status']}")
            print(f"  Binance Connection: {health['binance_connection']}")
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"❌ Exception: {str(e)}")

if __name__ == "__main__":
    print("🚀 Testing Live API Endpoints")
    print("=" * 50)

    # Run all tests
    test_health_check()
    test_live_tokens()
    test_specific_tokens()
    test_live_signals()
    test_token_details()
    test_market_overview()

    print("\n" + "=" * 50)
    print("✅ All tests completed!")
    print("\n📋 Available Endpoints:")
    print(f"  GET {BASE_URL}/tokens - Get live token data")
    print(f"  GET {BASE_URL}/tokens?symbols=DOGE,BTC - Get specific tokens")
    print(f"  GET {BASE_URL}/signals - Get trading signals")
    print(f"  GET {BASE_URL}/token/DOGE - Get DOGE details")
    print(f"  GET {BASE_URL}/market-overview - Get market overview")
    print(f"  GET {BASE_URL}/popular-tokens - Get popular tokens")
    print(f"  GET {BASE_URL}/trending - Get trending tokens")
    print(f"  GET {BASE_URL}/health - Health check")
