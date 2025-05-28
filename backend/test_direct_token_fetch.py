#!/usr/bin/env python3
"""
Direct test of the enhanced token management system
This script tests the OneInchService directly without needing the server running
"""

import sys
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.services.oneinch_service import OneInchService
from app.core.config import settings

def main():
    print("🚀 DIRECT TOKEN MANAGEMENT TEST")
    print("="*50)

    # Initialize the service
    print("1️⃣ Initializing OneInchService...")
    service = OneInchService()

    print(f"   API Key configured: {'✅' if service.api_key else '❌'}")
    print(f"   Chain ID: {service.chain_id}")
    print(f"   Total tokens loaded: {len(service.token_addresses)}")

    # Test token addresses
    print("\n2️⃣ Testing token addresses...")
    test_tokens = ['USDT', 'CAKE', 'ADA', 'BNB', 'ETH']

    for token in test_tokens:
        address = service.token_addresses.get(token)
        if address:
            print(f"   ✅ {token}: {address}")
        else:
            print(f"   ❌ {token}: Not found")

    # Test search functionality
    print("\n3️⃣ Testing token search...")
    try:
        results = service.search_tokens('CAKE', limit=3)
        print(f"   Found {len(results)} results for 'CAKE':")
        for result in results:
            print(f"     {result.get('symbol')}: {result.get('address')}")
    except Exception as e:
        print(f"   ❌ Search error: {str(e)}")

    # Test popular tokens
    print("\n4️⃣ Testing popular tokens...")
    try:
        popular = service.get_popular_tokens(limit=10)
        print(f"   Found {len(popular)} popular tokens:")
        for token in popular[:5]:
            print(f"     {token.get('symbol')}: {token.get('address')}")
    except Exception as e:
        print(f"   ❌ Popular tokens error: {str(e)}")

    # Test cache info
    print("\n5️⃣ Testing cache info...")
    try:
        cache_info = service.get_cache_info()
        print(f"   Cache exists: {cache_info.get('cache_exists', False)}")
        print(f"   Total tokens: {cache_info.get('total_tokens', 0)}")
        if 'cache_timestamp' in cache_info:
            print(f"   Cache timestamp: {cache_info['cache_timestamp']}")
    except Exception as e:
        print(f"   ❌ Cache info error: {str(e)}")

    # Test manual refresh
    print("\n6️⃣ Testing manual refresh...")
    try:
        total_tokens = service.refresh_token_addresses()
        print(f"   ✅ Refreshed! Total tokens: {total_tokens}")
    except Exception as e:
        print(f"   ❌ Refresh error: {str(e)}")

    # Show some random tokens
    print("\n7️⃣ Sample of available tokens:")
    count = 0
    for symbol, address in service.token_addresses.items():
        print(f"   {symbol}: {address}")
        count += 1
        if count >= 10:
            break

    print(f"\n🎯 SUMMARY:")
    print(f"   Total tokens available: {len(service.token_addresses)}")
    print(f"   API configured: {'✅' if service.api_key else '❌'}")
    print(f"   Cache file: {'✅' if service._token_cache_file.exists() else '❌'}")

    if len(service.token_addresses) > 50:
        print("   🚀 SUCCESS: Enhanced token management is working!")
    else:
        print("   ⚠️  WARNING: Using fallback tokens only")

if __name__ == "__main__":
    main()
