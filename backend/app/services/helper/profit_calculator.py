from typing import List, Dict, Tuple, Optional, Deque
from datetime import datetime, timedelta
from collections import deque
from app.core.logger import logger

class ProfitCalculator:
    @staticmethod
    def calculate_position_profit(
        trades: List[Dict],
        position_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict:
        """
        Calculate profits for trades using FIFO method, optionally filtered by position and time range

        Args:
            trades: List of trade dictionaries with required fields
            position_id: Optional position ID to filter trades
            start_time: Optional start time to filter trades
            end_time: Optional end time to filter trades

        Returns:
            Dictionary containing profit calculations and details
        """
        # Filter trades by position if provided
        if position_id is not None:
            trades = [t for t in trades if t.get("position_id") == position_id]

        # Filter trades by time range if provided
        if start_time is not None:
            trades = [t for t in trades if t.get("timestamp") >= start_time]
        if end_time is not None:
            trades = [t for t in trades if t.get("timestamp") <= end_time]

        # Sort trades by timestamp (oldest first)
        # Filter out trades with None timestamps and sort the rest
        trades = [t for t in trades if t.get("timestamp") is not None]
        trades = sorted(trades, key=lambda x: x.get("timestamp"))

        # Initialize holding queues for each symbol
        holdings = {}  # symbol -> deque of (amount, rate)

        # Initialize results
        results = {
            "total_profit": 0.0,
            "total_fee": 0.0,
            "trade_profits": [],
            "symbols_traded": set(),
            "positions": set(),
            "start_time": start_time,
            "end_time": end_time,
        }

        # Update start_time and end_time from trades if available
        if trades:
            if not start_time and trades[0].get("timestamp"):
                results["start_time"] = trades[0].get("timestamp")
            if not end_time and trades[-1].get("timestamp"):
                results["end_time"] = trades[-1].get("timestamp")

        for trade in trades:
            symbol = trade.get("symbol")
            side = trade.get("side")
            amount = trade.get("quantity", 0)
            price = trade.get("price", 0)
            fee = trade.get("fee", 0)
            timestamp = trade.get("timestamp")
            position_id = trade.get("position_id")

            # Add symbol and position ID to results for tracking
            results["symbols_traded"].add(symbol)
            if position_id:
                results["positions"].add(position_id)

            # Initialize holdings queue for this symbol if it doesn't exist
            if symbol not in holdings:
                holdings[symbol] = deque()  # list of (amount, price)

            if side == "BUY":
                # Add to holdings
                holdings[symbol].append((amount, price))
                logger.debug(f"Added {amount} {symbol} at {price} to holdings")
            elif side == "SELL":
                # Calculate profit using FIFO method
                sell_amount = amount
                sell_price = price
                sold_units = 0
                cost_basis = 0

                try:
                    while sell_amount > 0 and holdings[symbol]:
                        held_amount, held_price = holdings[symbol].popleft()
                        used_amount = min(sell_amount, held_amount)

                        # Add to cost basis
                        cost_basis += used_amount * held_price

                        # If we didn't use all of the held amount, put the remainder back
                        if held_amount > used_amount:
                            holdings[symbol].appendleft((held_amount - used_amount, held_price))

                        # Update tracking
                        sell_amount -= used_amount
                        sold_units += used_amount

                    # Calculate profit
                    sell_value = sold_units * sell_price
                    profit = sell_value - cost_basis - fee

                    # Update results
                    results["total_profit"] += profit
                    results["total_fee"] += fee

                    # Record this trade's profit details
                    trade_profit = {
                        "id": trade.get("id"),
                        "symbol": symbol,
                        "sell_amount": sold_units,
                        "sell_price": sell_price,
                        "cost_basis": cost_basis,
                        "sell_value": sell_value,
                        "fee": fee,
                        "profit": profit,
                        "profit_percent": (profit / cost_basis * 100) if cost_basis > 0 else 0,
                        "timestamp": timestamp,
                        "position_id": position_id
                    }
                    results["trade_profits"].append(trade_profit)

                    logger.info(f"Calculated profit for {sold_units} {symbol} at {sell_price}: ${profit:.2f}")

                except Exception as e:
                    logger.error(f"Error calculating profit for {symbol}: {str(e)}")

            # Add the total fee to the results
            results["total_fee"] += fee

        # Calculate some additional metrics
        results["symbols_traded"] = list(results["symbols_traded"])
        results["positions"] = list(results["positions"])
        results["trade_count"] = len(trades)
        results["profitable_trades"] = sum(1 for tp in results["trade_profits"] if tp["profit"] > 0)
        results["loss_trades"] = sum(1 for tp in results["trade_profits"] if tp["profit"] < 0)

        # Calculate average profit per trade if there are any profit trades
        if results["trade_profits"]:
            results["avg_profit_per_trade"] = results["total_profit"] / len(results["trade_profits"])
        else:
            results["avg_profit_per_trade"] = 0

        # Calculate remaining holdings
        results["remaining_holdings"] = {}
        for symbol, symbol_holdings in holdings.items():
            if symbol_holdings:
                total_amount = sum(amount for amount, _ in symbol_holdings)
                avg_price = sum(amount * price for amount, price in symbol_holdings) / total_amount if total_amount > 0 else 0
                results["remaining_holdings"][symbol] = {
                    "total_amount": total_amount,
                    "avg_price": avg_price
                }

        return results

    @staticmethod
    def calculate_swap_profits(
        swaps: List[Dict],
        position_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict:
        """
        Calculate profits from swap transactions using FIFO method

        Args:
            swaps: List of swap dictionaries
            position_id: Optional position ID to filter swaps
            start_time: Optional start time to filter swaps
            end_time: Optional end time to filter swaps

        Returns:
            Dictionary containing profit calculations and details
        """
        # Filter swaps by position if provided
        if position_id is not None:
            swaps = [s for s in swaps if s.get("position_id") == position_id]

        # Filter swaps by time range if provided
        if start_time is not None:
            swaps = [s for s in swaps if s.get("timestamp") >= start_time]
        if end_time is not None:
            swaps = [s for s in swaps if s.get("timestamp") <= end_time]

        # Sort swaps by timestamp (oldest first)
        # Filter out swaps with None timestamps and sort the rest
        swaps = [s for s in swaps if s.get("timestamp") is not None]
        swaps = sorted(swaps, key=lambda x: x.get("timestamp"))

        # Initialize holdings for each symbol
        holdings = {}  # symbol -> deque of (amount, rate)

        # Initialize results
        results = {
            "total_profit": 0.0,
            "total_fee": 0.0,
            "swap_profits": [],
            "symbols_swapped": set(),
            "start_time": start_time,
            "end_time": end_time,
        }

        # Update start_time and end_time from swaps if available
        if swaps:
            if not start_time and swaps[0].get("timestamp"):
                results["start_time"] = swaps[0].get("timestamp")
            if not end_time and swaps[-1].get("timestamp"):
                results["end_time"] = swaps[-1].get("timestamp")

        for swap in swaps:
            from_symbol = swap.get("from_symbol", "")
            to_symbol = swap.get("to_symbol", "")
            from_amount = swap.get("from_amount", 0)
            to_amount = swap.get("to_amount", 0)
            rate = swap.get("rate", 0)
            fee = swap.get("fee", 0)
            timestamp = swap.get("timestamp")

            # Add symbols to results for tracking
            results["symbols_swapped"].add(from_symbol)
            results["symbols_swapped"].add(to_symbol)

            # Initialize holdings queues if they don't exist
            if from_symbol not in holdings:
                holdings[from_symbol] = deque()
            if to_symbol not in holdings:
                holdings[to_symbol] = deque()

            # Handle "buying" crypto (from stablecoin to crypto)
            if "USDT" in from_symbol or "USDC" in from_symbol or "BUSD" in from_symbol:
                # We're buying with a stablecoin, add to holdings
                holdings[to_symbol].append((to_amount, from_amount / to_amount))
                logger.debug(f"Added {to_amount} {to_symbol} at {from_amount / to_amount} to holdings (from swap)")

            # Handle "selling" crypto (from crypto to stablecoin)
            elif "USDT" in to_symbol or "USDC" in to_symbol or "BUSD" in to_symbol:
                # We're selling crypto for a stablecoin, calculate profit
                sell_amount = from_amount
                sell_value = to_amount
                sell_rate = sell_value / sell_amount
                sold_units = 0
                cost_basis = 0

                try:
                    while sell_amount > 0 and holdings[from_symbol]:
                        held_amount, held_rate = holdings[from_symbol].popleft()
                        used_amount = min(sell_amount, held_amount)

                        # Add to cost basis
                        cost_basis += used_amount * held_rate

                        # If we didn't use all of the held amount, put the remainder back
                        if held_amount > used_amount:
                            holdings[from_symbol].appendleft((held_amount - used_amount, held_rate))

                        # Update tracking
                        sell_amount -= used_amount
                        sold_units += used_amount

                    # Calculate profit
                    profit = sell_value - cost_basis - fee

                    # Update results
                    results["total_profit"] += profit
                    results["total_fee"] += fee

                    # Record this swap's profit details
                    swap_profit = {
                        "id": swap.get("id"),
                        "from_symbol": from_symbol,
                        "to_symbol": to_symbol,
                        "sell_amount": sold_units,
                        "sell_rate": sell_rate,
                        "cost_basis": cost_basis,
                        "sell_value": sell_value,
                        "fee": fee,
                        "profit": profit,
                        "profit_percent": (profit / cost_basis * 100) if cost_basis > 0 else 0,
                        "timestamp": timestamp
                    }
                    results["swap_profits"].append(swap_profit)

                    logger.info(f"Calculated swap profit for {sold_units} {from_symbol}: ${profit:.2f}")

                except Exception as e:
                    logger.error(f"Error calculating swap profit for {from_symbol}: {str(e)}")

            # For crypto-to-crypto swaps
            else:
                # This is a direct crypto-to-crypto swap
                # First calculate the cost basis of the crypto we're swapping away
                swap_amount = from_amount
                swapped_units = 0
                cost_basis = 0

                try:
                    while swap_amount > 0 and holdings[from_symbol]:
                        held_amount, held_rate = holdings[from_symbol].popleft()
                        used_amount = min(swap_amount, held_amount)

                        # Add to cost basis
                        cost_basis += used_amount * held_rate

                        # If we didn't use all of the held amount, put the remainder back
                        if held_amount > used_amount:
                            holdings[from_symbol].appendleft((held_amount - used_amount, held_rate))

                        # Update tracking
                        swap_amount -= used_amount
                        swapped_units += used_amount

                    # Now add the new crypto to holdings with its cost basis
                    effective_rate = cost_basis / to_amount if to_amount > 0 else 0
                    holdings[to_symbol].append((to_amount, effective_rate))

                    # No immediate profit/loss for crypto-to-crypto swaps
                    # The profit/loss will be realized when the newly acquired crypto is sold

                    logger.info(f"Swapped {swapped_units} {from_symbol} for {to_amount} {to_symbol}")

                except Exception as e:
                    logger.error(f"Error processing crypto-to-crypto swap: {str(e)}")

            # Add the fee to the total
            results["total_fee"] += fee

        # Calculate some additional metrics
        results["symbols_swapped"] = list(results["symbols_swapped"])
        results["swap_count"] = len(swaps)
        results["profitable_swaps"] = sum(1 for sp in results["swap_profits"] if sp["profit"] > 0)
        results["loss_swaps"] = sum(1 for sp in results["swap_profits"] if sp["profit"] < 0)

        # Calculate average profit per swap if there are any profit swaps
        if results["swap_profits"]:
            results["avg_profit_per_swap"] = results["total_profit"] / len(results["swap_profits"])
        else:
            results["avg_profit_per_swap"] = 0

        # Calculate remaining holdings
        results["remaining_holdings"] = {}
        for symbol, symbol_holdings in holdings.items():
            if symbol_holdings:
                total_amount = sum(amount for amount, _ in symbol_holdings)
                avg_price = sum(amount * price for amount, price in symbol_holdings) / total_amount if total_amount > 0 else 0
                results["remaining_holdings"][symbol] = {
                    "total_amount": total_amount,
                    "avg_price": avg_price
                }

        return results

profit_calculator = ProfitCalculator()
