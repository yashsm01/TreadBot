from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from ..models.crypto import Cryptocurrency
import logging
import ccxt
from datetime import datetime
from sqlalchemy import update

logger = logging.getLogger(__name__)

class CryptoService:
    def __init__(self, db: Session):
        self.db = db
        self.exchange = ccxt.binance()

    async def sync_cryptocurrencies(self) -> None:
        """Sync cryptocurrency data from exchange"""
        try:
            # Fetch markets from exchange
            markets = self.exchange.fetch_markets()

            # Process only USDT pairs
            usdt_markets = [m for m in markets if m['quote'] == 'USDT']

            # Get existing symbols
            existing_cryptos = {
                crypto.symbol: crypto
                for crypto in self.db.query(Cryptocurrency).all()
            }

            # Track processed symbols to mark inactive ones
            processed_symbols = set()

            for market in usdt_markets:
                try:
                    symbol = f"{market['base']}/USDT"
                    processed_symbols.add(symbol)

                    crypto_data = {
                        'symbol': symbol,
                        'name': market.get('info', {}).get('baseAsset', market['base']),
                        'is_active': True,
                        'min_quantity': float(market['limits']['amount']['min']) if market['limits']['amount']['min'] else 0.0,
                        'price_precision': market['precision']['price'],
                        'quantity_precision': market['precision']['amount'],
                        'updated_at': datetime.now()
                    }

                    if symbol in existing_cryptos:
                        # Update existing record
                        crypto = existing_cryptos[symbol]
                        for key, value in crypto_data.items():
                            setattr(crypto, key, value)
                    else:
                        # Create new record
                        crypto = Cryptocurrency(**crypto_data)
                        self.db.add(crypto)

                except Exception as e:
                    logger.error(f"Error processing market {market['symbol']}: {str(e)}")
                    continue

            # Mark unprocessed symbols as inactive
            for symbol, crypto in existing_cryptos.items():
                if symbol not in processed_symbols:
                    crypto.is_active = False
                    crypto.updated_at = datetime.now()

            # Commit all changes
            self.db.commit()
            logger.info(f"Cryptocurrency sync completed successfully. Processed {len(processed_symbols)} pairs.")

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error syncing cryptocurrencies: {str(e)}")
            raise

    def get_all_active_pairs(self) -> List[str]:
        """Get all active trading pairs"""
        try:
            cryptos = self.db.query(Cryptocurrency).filter(
                Cryptocurrency.is_active == True
            ).all()
            return [crypto.symbol for crypto in cryptos]
        except Exception as e:
            logger.error(f"Error getting active pairs: {str(e)}")
            return []

    def get_crypto_by_symbol(self, symbol: str) -> Optional[Cryptocurrency]:
        """Get cryptocurrency by symbol"""
        try:
            return self.db.query(Cryptocurrency).filter(
                Cryptocurrency.symbol == symbol,
                Cryptocurrency.is_active == True
            ).first()
        except Exception as e:
            logger.error(f"Error getting crypto by symbol {symbol}: {str(e)}")
            return None

    def validate_trading_pair(self, symbol: str) -> bool:
        """Validate if a trading pair exists and is active"""
        crypto = self.get_crypto_by_symbol(symbol)
        return crypto is not None and crypto.is_active

    def get_precision_info(self, symbol: str) -> tuple:
        """Get price and quantity precision for a symbol"""
        crypto = self.get_crypto_by_symbol(symbol)
        if crypto:
            return crypto.price_precision, crypto.quantity_precision
        return 8, 8  # Default precision if not found

    def get_min_quantity(self, symbol: str) -> float:
        """Get minimum trade quantity for a symbol"""
        crypto = self.get_crypto_by_symbol(symbol)
        if crypto:
            return crypto.min_quantity
        return 0.0  # Default if not found
