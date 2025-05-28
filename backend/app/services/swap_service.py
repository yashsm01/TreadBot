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


from app.services.oneinch_service import oneinch_service
import requests

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
                    # Calculate realized P/L for the sale (selling crypto for stablecoin)
                    # Handle edge cases where avg_buy_price might be 0 or None
                    avg_buy_price = existing_crypto.avg_buy_price or 0.0
                    realized_profit = (current_price - avg_buy_price) * quantity - fee_amount

                    # Get current cumulative realized profit (handle case where field might not exist)
                    current_realized_profit = getattr(existing_crypto, 'realized_profit', 0.0) or 0.0

                    # Log the P/L calculation details
                    logger.info(f"P/L Calculation for {symbol}: "
                              f"Sale price: {current_price}, "
                              f"Avg buy price: {avg_buy_price}, "
                              f"Quantity: {quantity}, "
                              f"Fee: {fee_amount}, "
                              f"Realized profit: {realized_profit}")

                    update_data = {
                        "quantity": existing_crypto.quantity - quantity,
                        "realized_profit": current_realized_profit + realized_profit,
                        "last_updated": transaction_time
                    }

                    if update_data["quantity"] <= 0:
                        # Keep in portfolio but set quantity to exactly 0
                        update_data["quantity"] = 0
                        await portfolio_crud.update(self.db, db_obj=existing_crypto, obj_in=update_data)
                        logger.info(f"Updated {symbol} portfolio quantity to 0 (keeping record), realized P/L: {realized_profit:.4f}")
                    else:
                        # Update with new quantity
                        await portfolio_crud.update(self.db, db_obj=existing_crypto, obj_in=update_data)
                        logger.info(f"Updated {symbol} portfolio: new quantity = {update_data['quantity']}, realized P/L: {realized_profit:.4f}")
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
                current_stable_profit = getattr(existing_stable, 'realized_profit', 0.0) or 0.0
                update_data = {
                    "quantity": existing_stable.quantity + stable_amount,
                    "realized_profit": current_stable_profit,  # Keep existing realized profit for stablecoin
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
                    realized_profit=0.0,  # Initialize realized profit for new stablecoin
                    last_updated=datetime.utcnow(),  # Fresh datetime
                    asset_type="STABLE",
                    user_id=1
                )

                # Add, commit and refresh directly
                self.db.add(new_stable_db)
                await self.db.commit()
                await self.db.refresh(new_stable_db)

                logger.info(f"Added {stable_coin} to portfolio with quantity {stable_amount}")

                # Set update_data for transaction details
                update_data = {
                    "quantity": stable_amount,
                    "realized_profit": 0.0,  # New stablecoin has no realized profit yet
                    "last_updated": transaction_time
                }

            # Log overall swap summary for P/L tracking
            profit_percentage = (realized_profit/abs(avg_buy_price * quantity))*100 if avg_buy_price > 0 else 0
            logger.info(f"SWAP SUMMARY - {symbol} to {stable_coin}: "
                       f"Sold {quantity} {symbol} at {current_price} "
                       f"(avg cost: {avg_buy_price}) = "
                       f"Realized P/L: {realized_profit:.4f} "
                       f"({profit_percentage:+.2f}% profit)")

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
                realized_profit=realized_profit,
                timestamp=datetime.utcnow(),  # Use a fresh datetime
                status="completed",
                user_id=1,
                position_id=position_id,
                to_stable=True
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
                "realized_profit": realized_profit,
                "cumulative_realized_profit": update_data["realized_profit"],
                "avg_buy_price": avg_buy_price,
                "status": "completed"
            }

            logger.info(f"Swap transaction stored in database: {transaction_details}")


            return {
                "status": "success",
                "message": f"Successfully swapped {quantity} {symbol} for {stable_amount} {stable_coin}",
                "transaction": transaction_details,
                "swap_transaction_id": transaction_details["transaction_id"],
                "profit_loss_info": {
                    "realized_profit": realized_profit,
                    "cumulative_realized_profit": update_data["realized_profit"],
                    "profit_percentage": (realized_profit / (avg_buy_price * quantity)) * 100 if avg_buy_price > 0 else 0,
                    "sale_price": current_price,
                    "original_avg_price": avg_buy_price
                }
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
                    # Get current cumulative realized profit for stablecoin (handle case where field might not exist)
                    current_stable_profit = getattr(existing_stable, 'realized_profit', 0.0) or 0.0

                    update_data = {
                        "quantity": existing_stable.quantity - amount,
                        "realized_profit": current_stable_profit,  # Keep existing realized profit for stablecoin
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

                # Get current cumulative realized profit (handle case where field might not exist)
                current_realized_profit = getattr(existing_crypto, 'realized_profit', 0.0) or 0.0

                # Update existing cryptocurrency entry
                update_data = {
                    "quantity": total_quantity,
                    "avg_buy_price": new_avg_price,
                    "realized_profit": current_realized_profit,  # Keep existing realized profit
                    "last_updated": transaction_time
                }
                await portfolio_crud.update(self.db, db_obj=existing_crypto, obj_in=update_data)
                logger.info(f"Updated {symbol} portfolio: new quantity = {total_quantity}, new avg price = {new_avg_price}")

                # For tracking purposes
                portfolio_realized_profit = current_realized_profit
                previous_avg_price = existing_crypto.avg_buy_price
            else:
                # Create new cryptocurrency entry directly using the database model
                # Create directly with database model to avoid serialization issues
                # Using Portfolio model imported earlier

                # Create a database model instance directly
                new_crypto_db = Portfolio(
                    symbol=symbol,
                    quantity=crypto_amount,
                    avg_buy_price=current_price,
                    realized_profit=0.0,  # Initialize realized profit for new crypto
                    last_updated=datetime.utcnow(),  # Fresh datetime
                    asset_type="CRYPTO",
                    user_id=1
                )

                # Add, commit and refresh directly
                self.db.add(new_crypto_db)
                await self.db.commit()
                await self.db.refresh(new_crypto_db)

                logger.info(f"Added {symbol} to portfolio with quantity {crypto_amount}")

                # For tracking purposes
                portfolio_realized_profit = 0.0
                previous_avg_price = current_price

            # Log overall swap summary for P/L tracking
            logger.info(f"SWAP SUMMARY - {stable_coin} to {symbol}: "
                       f"Bought {crypto_amount} {symbol} for {amount} {stable_coin} at {current_price} "
                       f"(new avg cost: {new_avg_price if existing_crypto else current_price}) "
                       f"Cumulative realized P/L: {portfolio_realized_profit:.4f}")

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
                realized_profit=portfolio_realized_profit,
                timestamp=datetime.utcnow(),  # Use a fresh datetime
                status="completed",
                user_id=1,
                position_id=position_id,
                to_stable=False
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
                "unrealized_profit": 0.0,  # No realized profit on purchase
                "cumulative_realized_profit": portfolio_realized_profit,
                "new_avg_buy_price": new_avg_price if existing_crypto else current_price,
                "previous_avg_price": previous_avg_price,
                "status": "completed"
            }

            logger.info(f"Swap transaction stored in database: {transaction_details}")

            return {
                "status": "success",
                "message": f"Successfully swapped {amount} {stable_coin} for {crypto_amount} {symbol}",
                "transaction": transaction_details,
                "cost_basis_info": {
                    "crypto_amount_received": crypto_amount,
                    "cost_per_unit": current_price,
                    "total_cost": amount,
                    "fees_paid": fee_amount,
                    "new_avg_buy_price": new_avg_price if existing_crypto else current_price,
                    "previous_avg_price": previous_avg_price,
                    "cumulative_realized_profit": portfolio_realized_profit
                }
            }

        except Exception as e:
            logger.error(f"Error swapping {stable_coin} to {symbol}: {e}")
            return {
                "status": "error",
                "message": f"Swap failed: {str(e)}",
                "error_details": str(e)
            }

    async def get_token(self):
        """Get available tokens from 1inch API"""
        try:
            if not settings.SWAP_ENABLED:
                return {"status": "disabled", "message": "Swaps are disabled"}

            # Use the 1inch tokens endpoint
            url = f"https://api.1inch.dev/swap/v6.0/{oneinch_service.chain_id}/tokens"

            response = requests.get(url, headers=oneinch_service.headers)
            response.raise_for_status()

            tokens_data = response.json()
            tokens = tokens_data.get('tokens', {})

            logger.info(f"Found {len(tokens)} tokens on chain {oneinch_service.chain_id}")

            # Return formatted token list
            formatted_tokens = []
            for token_address, token_info in list(tokens.items())[:10]:  # Limit to first 10 for example
                formatted_tokens.append({
                    "address": token_address,
                    "symbol": token_info.get('symbol'),
                    "name": token_info.get('name'),
                    "decimals": token_info.get('decimals')
                })

            return {
                "status": "success",
                "total_tokens": len(tokens),
                "sample_tokens": formatted_tokens,
                "chain_id": oneinch_service.chain_id
            }

        except Exception as e:
            logger.error(f"Error getting tokens: {e}")
            return {"status": "error", "message": f"Error getting tokens: {str(e)}"}

    async def execute_real_swap(self,
                               from_symbol: str,
                               to_symbol: str,
                               amount: float,
                               position_id: int) -> Dict:
        """Execute real swap using 1inch API"""
        try:
            if not settings.SWAP_ENABLED:
                logger.warning("Real swaps are disabled, using simulation")
                return await self.simulate_swap(from_symbol, to_symbol, amount, position_id)

            # Convert amount to wei (assuming 18 decimals for most tokens)
            amount_wei = str(int(amount * 10**18))

            # Execute swap via 1inch
            if to_symbol in ['USDT', 'USDC', 'BUSD']:
                # Crypto to stable
                result = await oneinch_service.swap_crypto_to_stable(
                    crypto_symbol=from_symbol,
                    stable_symbol=to_symbol,
                    amount=amount_wei,
                    slippage=settings.DEFAULT_SLIPPAGE
                )
            else:
                # Stable to crypto or crypto to crypto
                result = await oneinch_service.execute_swap(
                    src_token=oneinch_service.get_token_address(from_symbol),
                    dst_token=oneinch_service.get_token_address(to_symbol),
                    amount=amount_wei,
                    slippage=settings.DEFAULT_SLIPPAGE
                )

            if result.get("success"):
                # Create swap transaction record
                swap_transaction = SwapTransactionCreate(
                    from_symbol=from_symbol,
                    to_symbol=to_symbol,
                    from_amount=amount,
                    to_amount=0,  # Will be updated when transaction is confirmed
                    exchange_rate=0,  # Will be calculated
                    transaction_hash=result.get("swap_tx_hash"),
                    status="PENDING",
                    position_id=position_id,
                    swap_type="REAL_1INCH"
                )

                swap_record = await swap_transaction_crud.create(self.db, obj_in=swap_transaction)

                logger.info(f"Real swap executed: {from_symbol} -> {to_symbol}, TX: {result.get('swap_tx_hash')}")

                return {
                    "success": True,
                    "transaction": {
                        "transaction_id": swap_record.id,
                        "transaction_hash": result.get("swap_tx_hash"),
                        "from_symbol": from_symbol,
                        "to_symbol": to_symbol,
                        "from_amount": amount,
                        "status": "PENDING",
                        "swap_type": "REAL_1INCH"
                    },
                    "oneinch_result": result
                }
            else:
                logger.error(f"1inch swap failed: {result.get('error')}")
                # Fallback to simulation
                return await self.simulate_swap(from_symbol, to_symbol, amount, position_id)

        except Exception as e:
            logger.error(f"Error in real swap execution: {str(e)}")
            # Fallback to simulation
            return await self.simulate_swap(from_symbol, to_symbol, amount, position_id)

    async def simulate_swap(self,
                           from_symbol: str,
                           to_symbol: str,
                           amount: float,
                           position_id: int) -> Dict:
        """Simulate swap without actual execution (fallback method)"""
        try:
            logger.info(f"Simulating swap: {amount} {from_symbol} -> {to_symbol}")

            # Use existing swap logic but mark as simulation
            if to_symbol in ['USDT', 'USDC', 'BUSD']:
                # Crypto to stable simulation
                result = await self.swap_symbol_stable_coin(
                    symbol=from_symbol,
                    quantity=amount,
                    current_price=None,  # Will be fetched
                    target_stablecoin=to_symbol,
                    position_id=position_id
                )
            else:
                # Stable to crypto simulation
                result = await self.swap_stable_coin_symbol(
                    stable_coin=from_symbol,
                    symbol=to_symbol,
                    amount=amount,
                    position_id=position_id
                )

            # Mark as simulation
            if result.get("status") == "success":
                result["swap_type"] = "SIMULATION"
                result["transaction"]["swap_type"] = "SIMULATION"
                logger.info(f"Simulation completed: {from_symbol} -> {to_symbol}")

            return result

        except Exception as e:
            logger.error(f"Error in swap simulation: {str(e)}")
            return {
                "success": False,
                "status": "error",
                "error": str(e),
                "swap_type": "SIMULATION"
            }

    async def get_swap_quote(self,
                            from_symbol: str,
                            to_symbol: str,
                            amount: float) -> Dict:
        """Get swap quote from 1inch"""
        try:
            if not settings.SWAP_ENABLED:
                return {"error": "Swaps are disabled"}

            amount_wei = str(int(amount * 10**18))
            src_token = oneinch_service.get_token_address(from_symbol)
            dst_token = oneinch_service.get_token_address(to_symbol)

            quote = await oneinch_service.get_quote(src_token, dst_token, amount_wei)

            # Convert back from wei
            dst_amount = float(quote.get("dstAmount", 0)) / 10**18

            return {
                "success": True,
                "from_symbol": from_symbol,
                "to_symbol": to_symbol,
                "from_amount": amount,
                "to_amount": dst_amount,
                "exchange_rate": dst_amount / amount if amount > 0 else 0,
                "quote_data": quote
            }

        except Exception as e:
            logger.error(f"Error getting swap quote: {str(e)}")
            return {"success": False, "error": str(e)}

swap_service = SwapService(None)

