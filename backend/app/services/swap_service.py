from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from app.core.logger import logger
from app.core.config import settings
from app.crud.crud_trade import trade as trade_crud
from app.crud.crud_portfolio import portfolio as portfolio_crud
from app.services.helper.heplers import helpers
from app.services.helper.binance_helper import binance_helper
from app.schemas.portfolio import PortfolioCreate, PortfolioUpdate


class SwapService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def swap_symbol_stable_coin(self, symbol: str, quantity: float, current_price: float) -> Dict[str, Any]:
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
            existing_crypto = await portfolio_crud.get_by_symbol(self.db, symbol=symbol)

            if existing_crypto:
                # Update existing entry - reduce quantity
                if existing_crypto.quantity >= quantity:
                    update_data = {
                        "quantity": existing_crypto.quantity - quantity,
                        "last_updated": transaction_time
                    }

                    if update_data["quantity"] <= 0:
                        # Remove from portfolio if quantity is zero
                        await portfolio_crud.remove(self.db, id=existing_crypto.id)
                        logger.info(f"Removed {symbol} from portfolio as balance is now zero")
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
            existing_stable = await portfolio_crud.get_by_symbol(self.db, symbol=stable_coin)

            if existing_stable:
                # Update existing stablecoin entry
                update_data = {
                    "quantity": existing_stable.quantity + stable_amount,
                    "last_updated": transaction_time
                }
                await portfolio_crud.update(self.db, db_obj=existing_stable, obj_in=update_data)
                logger.info(f"Updated {stable_coin} portfolio: new quantity = {update_data['quantity']}")
            else:
                # Create new stablecoin entry
                new_stable = PortfolioCreate(
                    symbol=stable_coin,
                    quantity=stable_amount,
                    entry_price=1.0,  # Stablecoins are pegged to 1.0
                    asset_type="STABLE",
                    last_updated=transaction_time
                )
                await portfolio_crud.create(self.db, obj_in=new_stable)
                logger.info(f"Added {stable_coin} to portfolio with quantity {stable_amount}")

            # Record the transaction details
            transaction_details = {
                "transaction_id": helpers.generate_transaction_id(),
                "from_symbol": symbol,
                "to_symbol": stable_coin,
                "from_amount": quantity,
                "to_amount": stable_amount,
                "rate": current_price,
                "fee_percentage": fee_percentage,
                "fee_amount": fee_amount,
                "timestamp": transaction_time.isoformat(),
                "status": "completed"
            }

            # In a real implementation, you might store this in a transactions table
            logger.info(f"Swap transaction completed: {transaction_details}")

            return {
                "status": "success",
                "message": f"Successfully swapped {quantity} {symbol} for {stable_amount} {stable_coin}",
                "transaction": transaction_details
            }

        except Exception as e:
            logger.error(f"Error swapping {symbol} to stablecoin: {e}")
            return {
                "status": "error",
                "message": f"Swap failed: {str(e)}",
                "error_details": str(e)
            }

    async def swap_stable_coin_symbol(self, stable_coin: str, symbol: str, amount: float) -> Dict[str, Any]:
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
            existing_stable = await portfolio_crud.get_by_symbol(self.db, symbol=stable_coin)

            if existing_stable:
                # Update existing entry - reduce stablecoin quantity
                if existing_stable.quantity >= amount:
                    update_data = {
                        "quantity": existing_stable.quantity - amount,
                        "last_updated": transaction_time
                    }

                    if update_data["quantity"] <= 0:
                        # Remove from portfolio if quantity is zero
                        await portfolio_crud.remove(self.db, id=existing_stable.id)
                        logger.info(f"Removed {stable_coin} from portfolio as balance is now zero")
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
            existing_crypto = await portfolio_crud.get_by_symbol(self.db, symbol=symbol)

            if existing_crypto:
                # Calculate new average entry price
                total_value_before = existing_crypto.quantity * existing_crypto.entry_price
                new_value = amount - fee_amount
                total_quantity = existing_crypto.quantity + crypto_amount
                new_avg_price = (total_value_before + new_value) / total_quantity

                # Update existing cryptocurrency entry
                update_data = {
                    "quantity": total_quantity,
                    "entry_price": new_avg_price,
                    "last_updated": transaction_time
                }
                await portfolio_crud.update(self.db, db_obj=existing_crypto, obj_in=update_data)
                logger.info(f"Updated {symbol} portfolio: new quantity = {total_quantity}, new avg price = {new_avg_price}")
            else:
                # Create new cryptocurrency entry
                new_crypto = PortfolioCreate(
                    symbol=symbol,
                    quantity=crypto_amount,
                    entry_price=current_price,
                    asset_type="CRYPTO",
                    last_updated=transaction_time
                )
                await portfolio_crud.create(self.db, obj_in=new_crypto)
                logger.info(f"Added {symbol} to portfolio with quantity {crypto_amount}")

            # Record the transaction details
            transaction_details = {
                "transaction_id": helpers.generate_transaction_id(),
                "from_symbol": stable_coin,
                "to_symbol": symbol,
                "from_amount": amount,
                "to_amount": crypto_amount,
                "rate": current_price,
                "fee_percentage": fee_percentage,
                "fee_amount": fee_amount,
                "timestamp": transaction_time.isoformat(),
                "status": "completed"
            }

            # In a real implementation, you might store this in a transactions table
            logger.info(f"Swap transaction completed: {transaction_details}")

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

swap_service = SwapService()

