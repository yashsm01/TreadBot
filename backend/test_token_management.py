#!/usr/bin/env python3
"""
Test script for enhanced token management features
This script demonstrates the new dynamic token fetching and caching capabilities
"""

import asyncio
import requests
import json
import sys
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logger import logger

# Base URL for your API
BASE_URL = "http://localhost:8000/api/v1/swap"

def test_api_endpoint(endpoint, method="GET", data=None):
    """Test an API endpoint and return the response"""
    try:
        url = f"{BASE_URL}{endpoint}"

        if method == "GET":
            response = requests.get(url, timeout=30)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=30)

        print(f"\n🔗 {method} {endpoint}")
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("✅ Success!")
            return result
        else:
            print(f"❌ Error: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return None

def test_direct_1inch_api():
    """Test direct 1inch API access"""
    print("\n" + "="*60)
    print("🧪 TESTING DIRECT 1INCH API ACCESS")
    print("="*60)

    try:
        api_key = getattr(settings, 'ONEINCH_API_KEY', '')
        if not api_key:
            print("❌ No 1inch API key found in settings")
            return False

        # Test the exact endpoint from your example
        url = "https://api.1inch.dev/swap/v6.0/56/tokens"
        headers = {
            "Authorization": f"Bearer {api_key}"
        }

        print(f"🔗 GET {url}")
        response = requests.get(url, headers=headers, timeout=30)

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            tokens = data.get('tokens', {})

            print(f"✅ Success! Found {len(tokens)} tokens")

            # Show some example tokens
            print("\n📋 Sample tokens:")
            count = 0
            for address, info in tokens.items():
                symbol = info.get('symbol', 'Unknown')
                name = info.get('name', 'Unknown')
                print(f"  {symbol}: {address} ({name})")
                count += 1
                if count >= 10:  # Show first 10
                    break

            # Look for specific tokens
            print("\n🔍 Looking for specific tokens:")
            target_tokens = ['USDT', 'CAKE', 'ADA', 'BNB', 'ETH']

            for target in target_tokens:
                found = False
                for address, info in tokens.items():
                    if info.get('symbol', '').upper() == target:
                        print(f"  ✅ {target}: {address}")
                        found = True
                        break
                if not found:
                    print(f"  ❌ {target}: Not found")

            return True
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def test_token_management_endpoints():
    """Test all the new token management endpoints"""
    print("\n" + "="*60)
    print("🧪 TESTING TOKEN MANAGEMENT ENDPOINTS")
    print("="*60)

    # Test cache info
    print("\n1️⃣ Testing cache info...")
    cache_info = test_api_endpoint("/tokens/cache/info")
    if cache_info:
        print(f"   Cache exists: {cache_info.get('cache_info', {}).get('cache_exists', False)}")
        print(f"   Total tokens: {cache_info.get('cache_info', {}).get('total_tokens', 0)}")

    # Test cache refresh
    print("\n2️⃣ Testing cache refresh...")
    refresh_result = test_api_endpoint("/tokens/cache/refresh", method="POST")
    if refresh_result:
        print(f"   Refreshed tokens: {refresh_result.get('total_tokens', 0)}")

    # Test popular tokens
    print("\n3️⃣ Testing popular tokens...")
    popular_tokens = test_api_endpoint("/tokens/popular?limit=10")
    if popular_tokens:
        print(f"   Found {len(popular_tokens.get('popular_tokens', []))} popular tokens:")
        for token in popular_tokens.get('popular_tokens', [])[:5]:
            print(f"     {token.get('symbol')}: {token.get('address')}")

    # Test token search
    print("\n4️⃣ Testing token search...")
    search_results = test_api_endpoint("/tokens/search?query=CAKE&limit=5")
    if search_results:
        print(f"   Found {len(search_results.get('results', []))} results for 'CAKE':")
        for result in search_results.get('results', []):
            print(f"     {result.get('symbol')}: {result.get('address')}")

    # Test specific token info
    print("\n5️⃣ Testing specific token info...")
    token_info = test_api_endpoint("/tokens/info/USDT")
    if token_info:
        info = token_info.get('token_info', {})
        print(f"   USDT Info:")
        print(f"     Address: {info.get('address')}")
        print(f"     Name: {info.get('name')}")
        print(f"     Decimals: {info.get('decimals')}")

    # Test all tokens with pagination
    print("\n6️⃣ Testing all tokens (paginated)...")
    all_tokens = test_api_endpoint("/tokens/all?page=1&per_page=10")
    if all_tokens:
        pagination = all_tokens.get('pagination', {})
        print(f"   Page 1 of {pagination.get('total_pages', 0)}")
        print(f"   Total tokens: {pagination.get('total_tokens', 0)}")
        print(f"   Sample tokens:")
        for token in all_tokens.get('tokens', [])[:5]:
            print(f"     {token.get('symbol')}: {token.get('address')}")

def test_existing_endpoints():
    """Test existing endpoints to ensure they still work"""
    print("\n" + "="*60)
    print("🧪 TESTING EXISTING ENDPOINTS")
    print("="*60)

    # Test health check
    print("\n1️⃣ Testing health check...")
    test_api_endpoint("/health-check")

    # Test available tokens (old endpoint)
    print("\n2️⃣ Testing available tokens (legacy)...")
    test_api_endpoint("/available-tokens")

    # Test status
    print("\n3️⃣ Testing status...")
    test_api_endpoint("/status")

def main():
    """Run all tests"""
    print("🚀 ENHANCED TOKEN MANAGEMENT TESTING")
    print("="*60)
    print("This script tests the new dynamic token fetching capabilities")
    print("Make sure your FastAPI server is running on localhost:8000")
    print("="*60)

    # Test direct 1inch API access first
    api_success = test_direct_1inch_api()

    # Test the new token management endpoints
    test_token_management_endpoints()

    # Test existing endpoints
    test_existing_endpoints()

    print("\n" + "="*60)
    print("🏁 TESTING COMPLETE")
    print("="*60)

    if api_success:
        print("✅ Direct 1inch API access: SUCCESS")
        print("✅ Your API key is working correctly")
        print("✅ You should see hundreds of tokens available")
    else:
        print("❌ Direct 1inch API access: FAILED")
        print("❌ Check your API key configuration")
        print("❌ The system will fall back to hardcoded tokens")

    print("\n💡 Next steps:")
    print("1. Check the token_addresses_cache.json file in your backend directory")
    print("2. The cache will automatically refresh every 24 hours")
    print("3. Use the new endpoints to search and discover tokens dynamically")
    print("4. Popular tokens are pre-filtered for easy access")

if __name__ == "__main__":
    main()
