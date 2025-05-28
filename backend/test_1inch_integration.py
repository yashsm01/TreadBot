#!/usr/bin/env python3
"""
Test script for 1inch integration
Run this to verify your 1inch setup is working correctly
"""

import asyncio
import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000/api/v1/swap"

async def test_1inch_integration():
    """Test all 1inch integration endpoints"""

    print("🚀 Testing 1inch Integration")
    print("=" * 50)

    tests = [
        {
            "name": "Health Check",
            "method": "GET",
            "url": f"{BASE_URL}/health-check",
            "description": "Comprehensive system health check"
        },
        {
            "name": "Status Check",
            "method": "GET",
            "url": f"{BASE_URL}/status",
            "description": "Basic status information"
        },
        {
            "name": "Supported Tokens",
            "method": "GET",
            "url": f"{BASE_URL}/tokens",
            "description": "Get list of supported tokens"
        },
        {
            "name": "Available Tokens",
            "method": "GET",
            "url": f"{BASE_URL}/available-tokens",
            "description": "Get tokens from 1inch API"
        },
        {
            "name": "Swap Quote",
            "method": "GET",
            "url": f"{BASE_URL}/quote?from_symbol=USDT&to_symbol=USDC&amount=100",
            "description": "Get swap quote for 100 USDT -> USDC"
        },
        {
            "name": "Test Connection",
            "method": "POST",
            "url": f"{BASE_URL}/test-connection",
            "description": "Test 1inch API connection"
        }
    ]

    results = []

    for test in tests:
        print(f"\n🧪 Testing: {test['name']}")
        print(f"   {test['description']}")

        try:
            if test['method'] == 'GET':
                response = requests.get(test['url'], timeout=10)
            else:
                response = requests.post(test['url'], timeout=10)

            if response.status_code == 200:
                data = response.json()
                success = data.get('success', False)

                if success:
                    print(f"   ✅ PASSED")

                    # Show specific results for some tests
                    if test['name'] == 'Health Check':
                        health_data = data.get('data', {})
                        config = health_data.get('configuration', {})
                        connectivity = health_data.get('connectivity', {})
                        errors = health_data.get('errors', [])

                        print(f"      Overall Status: {health_data.get('overall_status')}")
                        print(f"      API Key: {'✅' if config.get('api_key_configured') else '❌'}")
                        print(f"      Wallet: {'✅' if config.get('wallet_configured') else '❌'}")
                        print(f"      Web3: {'✅' if connectivity.get('web3_connected') else '❌'}")
                        print(f"      1inch API: {'✅' if connectivity.get('api_accessible') else '❌'}")

                        if errors:
                            print(f"      Errors: {', '.join(errors)}")

                    elif test['name'] == 'Swap Quote':
                        quote_data = data.get('data', {})
                        if quote_data.get('success'):
                            print(f"      Quote: {quote_data.get('from_amount')} {quote_data.get('from_symbol')} -> {quote_data.get('to_amount'):.6f} {quote_data.get('to_symbol')}")
                        else:
                            print(f"      Quote Error: {quote_data.get('error', 'Unknown error')}")

                    elif test['name'] == 'Supported Tokens':
                        token_data = data.get('data', {})
                        tokens = token_data.get('supported_tokens', {})
                        print(f"      Tokens: {len(tokens)} configured")
                        print(f"      Chain ID: {token_data.get('chain_id')}")
                        print(f"      Swap Enabled: {token_data.get('swap_enabled')}")

                else:
                    print(f"   ❌ FAILED: {data.get('error', 'Unknown error')}")

                results.append({
                    'test': test['name'],
                    'status': 'PASSED' if success else 'FAILED',
                    'response': data
                })

            else:
                print(f"   ❌ FAILED: HTTP {response.status_code}")
                results.append({
                    'test': test['name'],
                    'status': 'FAILED',
                    'error': f"HTTP {response.status_code}"
                })

        except requests.exceptions.ConnectionError:
            print(f"   ❌ FAILED: Cannot connect to server")
            print(f"      Make sure your FastAPI server is running on {BASE_URL}")
            results.append({
                'test': test['name'],
                'status': 'FAILED',
                'error': 'Connection error'
            })

        except Exception as e:
            print(f"   ❌ FAILED: {str(e)}")
            results.append({
                'test': test['name'],
                'status': 'FAILED',
                'error': str(e)
            })

    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)

    passed = sum(1 for r in results if r['status'] == 'PASSED')
    total = len(results)

    print(f"Tests Passed: {passed}/{total}")

    if passed == total:
        print("🎉 All tests passed! Your 1inch integration is working correctly.")
    elif passed > 0:
        print("⚠️  Some tests passed. Check the configuration for failed tests.")
    else:
        print("❌ All tests failed. Check your server and configuration.")

    print(f"\nTimestamp: {datetime.now().isoformat()}")

    # Configuration recommendations
    print("\n📝 CONFIGURATION RECOMMENDATIONS:")

    # Check if health check passed and get recommendations
    health_result = next((r for r in results if r['test'] == 'Health Check'), None)
    if health_result and health_result['status'] == 'PASSED':
        health_data = health_result['response'].get('data', {})
        config = health_data.get('configuration', {})
        errors = health_data.get('errors', [])

        if not config.get('api_key_configured'):
            print("   • Add ONEINCH_API_KEY to your .env file")

        if not config.get('wallet_configured'):
            print("   • Add WALLET_ADDRESS to your .env file")

        if not config.get('private_key_configured'):
            print("   • Add PRIVATE_KEY to your .env file (for real swaps)")

        if not config.get('swap_enabled'):
            print("   • Set SWAP_ENABLED=true to enable real swaps (optional)")

        if not errors:
            print("   • Configuration looks good! ✅")

    else:
        print("   • Make sure your FastAPI server is running")
        print("   • Check your .env file configuration")
        print("   • Review the setup guide in ONEINCH_SETUP.md")

if __name__ == "__main__":
    asyncio.run(test_1inch_integration())
