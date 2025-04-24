import sys
import os
import logging
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from backend.database import SessionLocal
from backend.models.crypto import Cryptocurrency
from sqlalchemy.exc import IntegrityError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def add_dummy_cryptocurrencies():
    """Add dummy cryptocurrency data to the database"""
    db = SessionLocal()

    # List of popular cryptocurrencies with realistic data
    cryptocurrencies = [
        {
            "symbol": "BTC/USDT",
            "name": "Bitcoin",
            "is_active": True,
            "min_quantity": 0.00001,  # $0.3 at $30,000
            "price_precision": 2,      # $30,000.00
            "quantity_precision": 6    # 0.000001 BTC
        },
        {
            "symbol": "ETH/USDT",
            "name": "Ethereum",
            "is_active": True,
            "min_quantity": 0.001,    # $2 at $2,000
            "price_precision": 2,      # $2,000.00
            "quantity_precision": 5    # 0.00001 ETH
        },
        {
            "symbol": "BNB/USDT",
            "name": "Binance Coin",
            "is_active": True,
            "min_quantity": 0.01,     # $2.5 at $250
            "price_precision": 2,      # $250.00
            "quantity_precision": 3    # 0.001 BNB
        },
        {
            "symbol": "SOL/USDT",
            "name": "Solana",
            "is_active": True,
            "min_quantity": 0.1,      # $10 at $100
            "price_precision": 3,      # $100.000
            "quantity_precision": 2    # 0.01 SOL
        },
        {
            "symbol": "ADA/USDT",
            "name": "Cardano",
            "is_active": True,
            "min_quantity": 1.0,      # $0.5 at $0.50
            "price_precision": 4,      # $0.5000
            "quantity_precision": 1    # 0.1 ADA
        },
        {
            "symbol": "XRP/USDT",
            "name": "Ripple",
            "is_active": True,
            "min_quantity": 1.0,      # $0.6 at $0.60
            "price_precision": 4,      # $0.6000
            "quantity_precision": 1    # 0.1 XRP
        },
        {
            "symbol": "DOGE/USDT",
            "name": "Dogecoin",
            "is_active": True,
            "min_quantity": 10.0,     # $0.7 at $0.07
            "price_precision": 6,      # $0.070000
            "quantity_precision": 0    # 1 DOGE
        },
        {
            "symbol": "DOT/USDT",
            "name": "Polkadot",
            "is_active": True,
            "min_quantity": 0.1,      # $0.5 at $5
            "price_precision": 3,      # $5.000
            "quantity_precision": 2    # 0.01 DOT
        },
        {
            "symbol": "MATIC/USDT",
            "name": "Polygon",
            "is_active": True,
            "min_quantity": 1.0,      # $0.8 at $0.80
            "price_precision": 4,      # $0.8000
            "quantity_precision": 0    # 1 MATIC
        },
        {
            "symbol": "AVAX/USDT",
            "name": "Avalanche",
            "is_active": True,
            "min_quantity": 0.1,      # $3 at $30
            "price_precision": 3,      # $30.000
            "quantity_precision": 2    # 0.01 AVAX
        }
    ]

    success_count = 0
    skip_count = 0
    error_count = 0

    try:
        # Add each cryptocurrency to the database
        for crypto_data in cryptocurrencies:
            try:
                # Check if cryptocurrency already exists
                existing_crypto = db.query(Cryptocurrency).filter_by(symbol=crypto_data["symbol"]).first()

                if not existing_crypto:
                    crypto = Cryptocurrency(**crypto_data)
                    db.add(crypto)
                    db.flush()  # Flush to check for validation errors
                    logger.info(f"Added {crypto_data['name']} ({crypto_data['symbol']})")
                    success_count += 1
                else:
                    logger.info(f"Skipped {crypto_data['name']} ({crypto_data['symbol']}) - already exists")
                    skip_count += 1

            except IntegrityError as e:
                logger.error(f"Database integrity error for {crypto_data['symbol']}: {str(e)}")
                db.rollback()
                error_count += 1
                continue

            except ValueError as e:
                logger.error(f"Validation error for {crypto_data['symbol']}: {str(e)}")
                db.rollback()
                error_count += 1
                continue

        # Commit all successful additions
        db.commit()
        logger.info(f"\nSummary:")
        logger.info(f"Successfully added: {success_count}")
        logger.info(f"Skipped (already exist): {skip_count}")
        logger.info(f"Errors: {error_count}")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    add_dummy_cryptocurrencies()
