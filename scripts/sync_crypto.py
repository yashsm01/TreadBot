import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine, Base
from backend.services.crypto_service import CryptoService
from backend.models.crypto import Cryptocurrency

async def main():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)

    print("Initializing database session...")
    db: Session = SessionLocal()

    try:
        print("Initializing crypto service...")
        crypto_service = CryptoService(db)

        print("Starting cryptocurrency sync...")
        await crypto_service.sync_cryptocurrencies()

        print("Sync completed successfully!")

        # Print summary
        active_pairs = crypto_service.get_all_active_pairs()
        print(f"\nTotal active trading pairs: {len(active_pairs)}")
        print("\nSupported trading pairs:")
        for pair in active_pairs:
            crypto = crypto_service.get_crypto_by_symbol(pair)
            print(f"- {pair} (min qty: {crypto.min_quantity}, price precision: {crypto.price_precision})")

    except Exception as e:
        print(f"Error during sync: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
