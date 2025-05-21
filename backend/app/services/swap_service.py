from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from app.core.logger import logger
from app.core.config import settings
from app.crud.crud_trade import trade as trade_crud
from app.crud.crud_portfolio import portfolio_crud as portfolio_crud
from app.crud.crud_swap_transaction import swap_transaction_crud
from app.services.helper.heplers import helpers
from app.services.helper.binance_helper import binance_helper
from app.schemas.portfolio import PortfolioCreate, PortfolioUpdate
from app.schemas.swap_transaction import SwapTransactionCreate
from app.models.portfolio import Portfolio  # Add import for direct database model usage
from app.models.swap_transaction import SwapTransaction  # Add import for swap transaction model
from app.crud.curd_crypto import insert_crypto_data_live

#middleware
from app.middleware.one_inch_token_handler import one_inch_client

class SwapService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def swap_symbol_stable_coin(self, symbol: str, quantity: float, current_price: float, target_stablecoin: str = "USDT", position_id: int = None) -> Dict[str, Any]:
        """
        Swap a cryptocurrency for the best available stablecoin

        Args:
            symbol: Trading pair symbol (e.g., 'BTC')
            quantity: Amount to swap
            current_price: Current price (can be None, will be fetched if not provided)

        Returns:
            Dictionary with swap details and status
        """
        try:
            # Get the current price of the symbol
            crypto_details = await binance_helper.get_price(symbol)
            current_price = crypto_details["price"]

            if target_stablecoin:
                stable_coin = target_stablecoin
            else:
                # Get the best stable coin to buy
                stable_coin_data = await binance_helper.get_best_stable_coin()
                stable_coin = stable_coin_data["best_stable"]

            # Check if swaps are allowed
            swap_status = True
            if settings.TESTING:
                swap_status = True
            else:
                # In production, we might have additional checks
                swap_status = True

            if not swap_status:
                return {"status": "failed", "message": "Swap is not allowed in this mode"}

            # Calculate the amount to receive (including fees)
            fee_percentage = settings.SWAP_FEE_PERCENTAGE if hasattr(settings, "SWAP_FEE_PERCENTAGE") else 0.1
            fee_amount = (quantity * current_price) * (fee_percentage / 100)
            stable_amount = (quantity * current_price) - fee_amount

            # Create transaction timestamp
            transaction_time = datetime.utcnow()

            # In a real implementation, we would call the exchange API here
            # For now, we'll simulate the swap

            # Update portfolio: remove the original crypto
            # First check if we have this crypto in portfolio
            existing_crypto = await portfolio_crud.get_by_user_and_symbol(self.db, symbol=symbol)

            if existing_crypto:
                # Update existing entry - reduce quantity
                if existing_crypto.quantity >= quantity:
                    update_data = {
                        "quantity": existing_crypto.quantity - quantity,
                        "last_updated": transaction_time
                    }

                    if update_data["quantity"] <= 0:
                        # Keep in portfolio but set quantity to exactly 0
                        update_data["quantity"] = 0
                        await portfolio_crud.update(self.db, db_obj=existing_crypto, obj_in=update_data)
                        logger.info(f"Updated {symbol} portfolio quantity to 0 (keeping record)")
                    else:
                        # Update with new quantity
                        await portfolio_crud.update(self.db, db_obj=existing_crypto, obj_in=update_data)
                        logger.info(f"Updated {symbol} portfolio: new quantity = {update_data['quantity']}")
                else:
                    return {
                        "status": "failed",
                        "message": f"Insufficient {symbol} balance. Available: {existing_crypto.quantity}, Requested: {quantity}"
                    }
            else:
                return {
                    "status": "failed",
                    "message": f"No {symbol} found in portfolio"
                }

            # Add or update stablecoin in portfolio
            existing_stable = await portfolio_crud.get_by_user_and_symbol(self.db, symbol=stable_coin)

            if existing_stable:
                # Update existing stablecoin entry
                update_data = {
                    "quantity": existing_stable.quantity + stable_amount,
                    "last_updated": transaction_time
                }
                await portfolio_crud.update(self.db, db_obj=existing_stable, obj_in=update_data)
                logger.info(f"Updated {stable_coin} portfolio: new quantity = {update_data['quantity']}")
            else:
                # Create new stablecoin entry directly using updated CRUD method
                # Create directly with database model to avoid serialization issues
                # Create a database model instance directly
                new_stable_db = Portfolio(
                    symbol=stable_coin,
                    quantity=stable_amount,
                    avg_buy_price=1.0,  # Stablecoins are pegged to 1.0
                    last_updated=datetime.utcnow(),  # Fresh datetime
                    asset_type="STABLE",
                    user_id=1
                )

                # Add, commit and refresh directly
                self.db.add(new_stable_db)
                await self.db.commit()
                await self.db.refresh(new_stable_db)

                logger.info(f"Added {stable_coin} to portfolio with quantity {stable_amount}")

            # Generate a transaction ID
            transaction_id = helpers.generate_transaction_id()

            # Create a database model instance directly to avoid any serialization issues
            swap_transaction_db = SwapTransaction(
                transaction_id=transaction_id,
                from_symbol=symbol,
                to_symbol=stable_coin,
                from_amount=quantity,
                to_amount=stable_amount,
                rate=current_price,
                fee_percentage=fee_percentage,
                fee_amount=fee_amount,
                timestamp=datetime.utcnow(),  # Use a fresh datetime
                status="completed",
                user_id=1,
                position_id=position_id
            )

            # Add, commit and refresh directly
            self.db.add(swap_transaction_db)
            await self.db.commit()
            await self.db.refresh(swap_transaction_db)

            result = await insert_crypto_data_live(self.db, symbol,swap_transaction_id=transaction_id)
            # Create transaction details for logging
            transaction_details = {
                "transaction_id": transaction_id,
                "from_symbol": symbol,
                "to_symbol": stable_coin,
                "from_amount": quantity,
                "to_amount": stable_amount,
                "rate": current_price,
                "fee_percentage": fee_percentage,
                "fee_amount": fee_amount,
                "status": "completed"
            }

            logger.info(f"Swap transaction stored in database: {transaction_details}")


            return {
                "status": "success",
                "message": f"Successfully swapped {quantity} {symbol} for {stable_amount} {stable_coin}",
                "transaction": transaction_details,
                "swap_transaction_id": transaction_details["transaction_id"]
            }

        except Exception as e:
            logger.error(f"Error swapping {symbol} to stablecoin: {e}")
            return {
                "status": "error",
                "message": f"Swap failed: {str(e)}",
                "error_details": str(e)
            }

    async def swap_stable_coin_symbol(self, stable_coin: str, symbol: str, amount: float, target_stablecoin: str = "USDT", position_id: int = None) -> Dict[str, Any]:
        """
        Swap from stablecoin to cryptocurrency

        Args:
            stable_coin: Stablecoin symbol (e.g., 'USDT')
            symbol: Target cryptocurrency symbol (e.g., 'BTC')
            amount: Amount of stablecoin to swap

        Returns:
            Dictionary with swap details and status
        """
        try:
            #get the current price of the symbol
            crypto_details = await binance_helper.get_price(symbol)
            current_price = crypto_details["price"]

            # Calculate the amount of crypto to receive (including fees)
            fee_percentage = settings.SWAP_FEE_PERCENTAGE if hasattr(settings, "SWAP_FEE_PERCENTAGE") else 0.1
            fee_amount = amount * (fee_percentage / 100)
            crypto_amount = (amount - fee_amount) / current_price

            # Create transaction timestamp
            transaction_time = datetime.utcnow()

            #check if swaps are allowed
            swap_status = True
            if settings.TESTING:
                swap_status = True
            else:
                # In production, we might have additional checks
                swap_status = True

            if not swap_status:
                return {"status": "failed", "message": "Swap is not allowed in this mode"}

            # Update portfolio: reduce stablecoin amount
            existing_stable = await portfolio_crud.get_by_user_and_symbol(self.db, symbol=stable_coin)

            if existing_stable:
                # Update existing entry - reduce stablecoin quantity
                if existing_stable.quantity >= amount:
                    update_data = {
                        "quantity": existing_stable.quantity - amount,
                        "last_updated": transaction_time
                    }

                    if update_data["quantity"] <= 0:
                        # Keep in portfolio but set quantity to exactly 0
                        update_data["quantity"] = 0
                        await portfolio_crud.update(self.db, db_obj=existing_stable, obj_in=update_data)
                        logger.info(f"Updated {stable_coin} portfolio quantity to 0 (keeping record)")
                    else:
                        # Update with new quantity
                        await portfolio_crud.update(self.db, db_obj=existing_stable, obj_in=update_data)
                        logger.info(f"Updated {stable_coin} portfolio: new quantity = {update_data['quantity']}")
                else:
                    return {
                        "status": "failed",
                        "message": f"Insufficient {stable_coin} balance. Available: {existing_stable.quantity}, Requested: {amount}"
                    }
            else:
                return {
                    "status": "failed",
                    "message": f"No {stable_coin} found in portfolio"
                }

            # Add or update cryptocurrency in portfolio
            existing_crypto = await portfolio_crud.get_by_user_and_symbol(self.db, symbol=symbol)

            if existing_crypto:
                # Calculate new average entry price
                total_value_before = existing_crypto.quantity * existing_crypto.avg_buy_price
                new_value = amount - fee_amount
                total_quantity = existing_crypto.quantity + crypto_amount
                new_avg_price = (total_value_before + new_value) / total_quantity

                # Update existing cryptocurrency entry
                update_data = {
                    "quantity": total_quantity,
                    "avg_buy_price": new_avg_price,
                    "last_updated": transaction_time
                }
                await portfolio_crud.update(self.db, db_obj=existing_crypto, obj_in=update_data)
                logger.info(f"Updated {symbol} portfolio: new quantity = {total_quantity}, new avg price = {new_avg_price}")
            else:
                # Create new cryptocurrency entry directly using the database model
                # Create directly with database model to avoid serialization issues
                # Using Portfolio model imported earlier

                # Create a database model instance directly
                new_crypto_db = Portfolio(
                    symbol=symbol,
                    quantity=crypto_amount,
                    avg_buy_price=current_price,
                    last_updated=datetime.utcnow(),  # Fresh datetime
                    asset_type="CRYPTO",
                    user_id=1
                )

                # Add, commit and refresh directly
                self.db.add(new_crypto_db)
                await self.db.commit()
                await self.db.refresh(new_crypto_db)

                logger.info(f"Added {symbol} to portfolio with quantity {crypto_amount}")

            # Generate a transaction ID
            transaction_id = helpers.generate_transaction_id()

            # Create a database model instance directly to avoid any serialization issues
            swap_transaction_db = SwapTransaction(
                transaction_id=transaction_id,
                from_symbol=stable_coin,
                to_symbol=symbol,
                from_amount=amount,
                to_amount=crypto_amount,
                rate=current_price,
                fee_percentage=fee_percentage,
                fee_amount=fee_amount,
                timestamp=datetime.utcnow(),  # Use a fresh datetime
                status="completed",
                user_id=1,
                position_id=position_id
            )

            # Add, commit and refresh directly
            self.db.add(swap_transaction_db)
            await self.db.commit()
            await self.db.refresh(swap_transaction_db)

            result = await insert_crypto_data_live(self.db, symbol,swap_transaction_id=transaction_id)
            # Create transaction details for logging
            transaction_details = {
                "transaction_id": transaction_id,
                "from_symbol": stable_coin,
                "to_symbol": symbol,
                "from_amount": amount,
                "to_amount": crypto_amount,
                "rate": current_price,
                "fee_percentage": fee_percentage,
                "fee_amount": fee_amount,
                "status": "completed"
            }

            logger.info(f"Swap transaction stored in database: {transaction_details}")

            return {
                "status": "success",
                "message": f"Successfully swapped {amount} {stable_coin} for {crypto_amount} {symbol}",
                "transaction": transaction_details
            }

        except Exception as e:
            logger.error(f"Error swapping {stable_coin} to {symbol}: {e}")
            return {
                "status": "error",
                "message": f"Swap failed: {str(e)}",
                "error_details": str(e)
            }

    async def get_token():
        try:
             # Get Ethereum (chain ID 1) tokens
            tokens = await one_inch_client.get("/swap/v5.2/1/tokens")
            print(f"Found {len(tokens.get('tokens', {}))} tokens on Ethereum")

            # Print the first 3 tokens for example
            for i, (token_address, token_info) in enumerate(list(tokens.get('tokens', {}).items())[:3]):
                print(f"Token {i+1}: {token_info.get('symbol')} - {token_info.get('name')}")

            return tokens
        except Exception as e:
            logger.error(f"Error getting tokens: {e}")
            return {"status": "error", "message": f"Error getting tokens: {str(e)}"}
swap_service = SwapService(None)

