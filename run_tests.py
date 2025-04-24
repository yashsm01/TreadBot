import os
import sys
import pytest

def setup_test_environment():
    """Setup test environment variables"""
    os.environ['TELEGRAM_BOT_TOKEN'] = '7816751552:AAEdH_pquW9QFyr_OghH3RxkDqtOTBT3LsQ'
    os.environ['TELEGRAM_CHAT_ID'] = '505504650'
    os.environ['POSTGRES_USER'] = 'postgres'
    os.environ['POSTGRES_PASSWORD'] = '1234'
    os.environ['POSTGRES_HOST'] = 'localhost'
    os.environ['POSTGRES_PORT'] = '5432'
    os.environ['POSTGRES_DB'] = 'crypto_trading_test'
    os.environ['DEFAULT_TRADING_PAIR'] = 'BTC/USDT'

def run_tests():
    """Run the test suite"""
    setup_test_environment()

    # Add the project root to Python path
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)

    # Run pytest with arguments
    args = [
        '-v',  # verbose output
        '--asyncio-mode=auto',  # enable async test mode
        'tests/test_telegram_bot.py',  # test file to run
    ]

    return pytest.main(args)

if __name__ == '__main__':
    sys.exit(run_tests())
