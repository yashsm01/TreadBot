from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from datetime import datetime
import ccxt
import logging
from ..models.crypto import Cryptocurrency, CryptoPair
from ..core.logger import logger

class CryptoService:
    def __init__(self, db: Session = None):
        """Initialize the crypto service"""
        self.db = db
        self.exchange = ccxt.binance()

    async def sync_cryptocurrencies(self) -> None:
        """Sync cryptocurrency data from exchange"""
        try:
            # Fetch markets from exchange
            markets = self.exchange.fetch_markets()

            # Process only USDT pairs
            usdt_markets = [m for m in markets if m['quote'] == 'USDT']

            # Create a dictionary to store unique market data by symbol
            unique_markets = {}
            for market in usdt_markets:
                symbol = f"{market['base']}/USDT"
                # Only keep the first occurrence of each symbol
                if symbol not in unique_markets:
                    unique_markets[symbol] = market

            # Get existing symbols
            existing_cryptos = {
                crypto.symbol: crypto
                for crypto in self.db.query(Cryptocurrency).all()
            }

            # Track processed symbols
            processed_symbols = set()

            for symbol, market in unique_markets.items():
                try:
                    processed_symbols.add(symbol)

                    crypto_data = {
                        'symbol': symbol,
                        'name': market.get('info', {}).get('baseAsset', market['base']),
                        'is_active': True,
                        'min_quantity': float(market['limits']['amount']['min']) if market['limits']['amount']['min'] else 0.0,
                        'price_precision': market['precision']['price'],
                        'quantity_precision': market['precision']['amount'],
                        'updated_at': datetime.utcnow()
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
                    crypto.updated_at = datetime.utcnow()

            # Commit changes
            self.db.commit()
            logger.info(f"Cryptocurrency sync completed. Processed {len(processed_symbols)} pairs.")

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error syncing cryptocurrencies: {str(e)}")
            raise

    def get_all_active_pairs(self) -> List[str]:
        """Get all active trading pairs from the database"""
        try:
            if not self.db:
                logger.warning("Database session not initialized")
                return []

            pairs = self.db.query(CryptoPair).filter(CryptoPair.is_active == True).all()
            return [pair.symbol for pair in pairs]
        except Exception as e:
            logger.error(f"Error getting active pairs: {str(e)}")
            return []

    def get_crypto_by_symbol(self, symbol: str) -> Optional[Cryptocurrency]:
        """Get cryptocurrency by symbol"""
        try:
            return self.db.query(Cryptocurrency).filter(
                Cryptocurrency.symbol == symbol
            ).first()
        except Exception as e:
            logger.error(f"Error fetching crypto by symbol {symbol}: {str(e)}")
            return None

    def validate_trading_pair(self, symbol: str) -> bool:
        """
        Validate if a trading pair exists in the database.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')

        Returns:
            bool: True if the trading pair exists and is active
        """
        try:
            if not self.db:
                logger.warning("Database session not initialized")
                return False

            pair = self.db.query(CryptoPair).filter(
                CryptoPair.symbol == symbol,
                CryptoPair.is_active == True
            ).first()
            return pair is not None
        except Exception as e:
            logger.error(f"Error validating trading pair {symbol}: {str(e)}")
            return False

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

    def add_trading_pair(self, symbol: str) -> bool:
        """
        Add a new trading pair to the database.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')

        Returns:
            bool: True if the pair was added successfully
        """
        try:
            if not self.db:
                logger.warning("Database session not initialized")
                return False

            # Check if pair already exists
            existing_pair = self.db.query(CryptoPair).filter(
                CryptoPair.symbol == symbol
            ).first()

            if existing_pair:
                if not existing_pair.is_active:
                    existing_pair.is_active = True
                    self.db.commit()
                return True

            # Create new pair
            new_pair = CryptoPair(symbol=symbol, is_active=True)
            self.db.add(new_pair)
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding trading pair {symbol}: {str(e)}")
            self.db.rollback()
            return False

    def deactivate_trading_pair(self, symbol: str) -> bool:
        """
        Deactivate a trading pair.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')

        Returns:
            bool: True if the pair was deactivated successfully
        """
        try:
            if not self.db:
                logger.warning("Database session not initialized")
                return False

            pair = self.db.query(CryptoPair).filter(
                CryptoPair.symbol == symbol
            ).first()

            if pair:
                pair.is_active = False
                self.db.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deactivating trading pair {symbol}: {str(e)}")
            self.db.rollback()
            return False

# Create singleton instance
crypto_service = CryptoService()
