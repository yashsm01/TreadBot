import requests
import asyncio
import json
import os
from typing import Dict, Optional, Any, List
from web3 import Web3
from app.core.logger import logger
from app.core.config import settings
from datetime import datetime, timedelta
from pathlib import Path

class OneInchService:
    def __init__(self):
        self.chain_id = getattr(settings, 'ONEINCH_CHAIN_ID', 56)  # BSC by default
        self.api_key = getattr(settings, 'ONEINCH_API_KEY', '')
        self.web3_rpc_url = getattr(settings, 'WEB3_RPC_URL', 'https://bsc-dataseed.binance.org')
        self.wallet_address = getattr(settings, 'WALLET_ADDRESS', '')
        self.private_key = getattr(settings, 'PRIVATE_KEY', '')

        # Check if configuration is complete
        self.is_configured = bool(self.api_key and self.wallet_address and self.private_key)

        # Initialize Web3 only if we have RPC URL
        self.web3 = None
        try:
            if self.web3_rpc_url:
                self.web3 = Web3(Web3.HTTPProvider(self.web3_rpc_url))
        except Exception as e:
            logger.warning(f"Failed to initialize Web3: {str(e)}")

        # API URLs
        self.api_base_url = f"https://api.1inch.dev/swap/v6.0/{self.chain_id}"
        self.broadcast_api_url = f"https://api.1inch.dev/tx-gateway/v1.1/{self.chain_id}/broadcast"

        # Headers for API requests
        self.headers = {
            "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
            "accept": "application/json",
            "Content-Type": "application/json"
        }

        # Token addresses - will be populated dynamically
        self.token_addresses = {}
        self._token_cache_file = Path("token_addresses_cache.json")
        self._cache_expiry_hours = 24  # Cache expires after 24 hours

        # Load cached tokens or fetch new ones
        self._load_token_addresses()

        # Fallback token addresses for BSC (in case API fails)
        self._fallback_tokens = {
            'USDT': '0x55d398326f99059fF775485246999027B3197955',
            'USDC': '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d',
            'BUSD': '0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56',
            'BNB': '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c',  # WBNB
            'ETH': '0x2170Ed0880ac9A755fd29B2688956BD959F933F8',   # ETH on BSC
            'BTC': '0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c',   # BTCB
        }

    def _load_token_addresses(self):
        """Load token addresses from cache or fetch from API"""
        try:
            # Try to load from cache first
            if self._token_cache_file.exists():
                with open(self._token_cache_file, 'r') as f:
                    cache_data = json.load(f)

                # Check if cache is still valid
                cache_time = datetime.fromisoformat(cache_data.get('timestamp', '2000-01-01'))
                if datetime.now() - cache_time < timedelta(hours=self._cache_expiry_hours):
                    self.token_addresses = cache_data.get('tokens', {})
                    logger.info(f"Loaded {len(self.token_addresses)} token addresses from cache")
                    return
                else:
                    logger.info("Token cache expired, fetching fresh data")

            # Cache doesn't exist or is expired, fetch from API
            self._fetch_token_addresses()

        except Exception as e:
            logger.error(f"Error loading token addresses: {str(e)}")
            # Use fallback tokens
            self.token_addresses = self._fallback_tokens.copy()
            logger.info(f"Using fallback token addresses: {len(self.token_addresses)} tokens")

    def _fetch_token_addresses(self):
        """Fetch token addresses from 1inch API"""
        try:
            if not self.api_key:
                logger.warning("No 1inch API key available, using fallback tokens")
                self.token_addresses = self._fallback_tokens.copy()
                return

            url = f"{self.api_base_url}/tokens"
            response = requests.get(url, headers=self.headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                token_map = {}

                # Convert the response to symbol -> address mapping
                for token_address, token_info in data.get('tokens', {}).items():
                    symbol = token_info.get('symbol', '').upper()
                    if symbol:  # Only add tokens with valid symbols
                        token_map[symbol] = token_address

                self.token_addresses = token_map

                # Save to cache
                cache_data = {
                    'timestamp': datetime.now().isoformat(),
                    'tokens': token_map,
                    'chain_id': self.chain_id,
                    'total_tokens': len(token_map)
                }

                with open(self._token_cache_file, 'w') as f:
                    json.dump(cache_data, f, indent=2)

                logger.info(f"Fetched and cached {len(token_map)} token addresses from 1inch API")

            else:
                logger.error(f"Failed to fetch tokens from 1inch API: {response.status_code}")
                # Use fallback tokens
                self.token_addresses = self._fallback_tokens.copy()

        except Exception as e:
            logger.error(f"Error fetching token addresses from API: {str(e)}")
            # Use fallback tokens
            self.token_addresses = self._fallback_tokens.copy()

    def refresh_token_addresses(self):
        """Manually refresh token addresses from API"""
        logger.info("Manually refreshing token addresses...")
        self._fetch_token_addresses()
        return len(self.token_addresses)

    def get_token_info(self, symbol: str) -> Dict[str, Any]:
        """Get detailed token information"""
        try:
            if not self.api_key:
                return {"error": "No API key configured"}

            url = f"{self.api_base_url}/tokens"
            response = requests.get(url, headers=self.headers, timeout=30)

            if response.status_code == 200:
                data = response.json()

                # Find token by symbol
                for token_address, token_info in data.get('tokens', {}).items():
                    if token_info.get('symbol', '').upper() == symbol.upper():
                        return {
                            "address": token_address,
                            "symbol": token_info.get('symbol'),
                            "name": token_info.get('name'),
                            "decimals": token_info.get('decimals'),
                            "logoURI": token_info.get('logoURI', ''),
                            "tags": token_info.get('tags', [])
                        }

                return {"error": f"Token {symbol} not found"}
            else:
                return {"error": f"API error: {response.status_code}"}

        except Exception as e:
            logger.error(f"Error getting token info: {str(e)}")
            return {"error": str(e)}

    def search_tokens(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for tokens by name or symbol"""
        try:
            results = []
            query_lower = query.lower()

            for symbol, address in self.token_addresses.items():
                if query_lower in symbol.lower():
                    # Get additional info if available
                    token_info = self.get_token_info(symbol)
                    if "error" not in token_info:
                        results.append(token_info)
                    else:
                        results.append({
                            "address": address,
                            "symbol": symbol,
                            "name": symbol,
                            "decimals": 18  # Default
                        })

                    if len(results) >= limit:
                        break

            return results

        except Exception as e:
            logger.error(f"Error searching tokens: {str(e)}")
            return []

    def get_popular_tokens(self, limit: int = 20) -> List[Dict[str, str]]:
        """Get list of popular tokens"""
        # Define popular tokens on BSC
        popular_symbols = [
            'BNB', 'USDT', 'USDC', 'BUSD', 'ETH', 'BTC', 'CAKE', 'ADA', 'DOT', 'LINK',
            'XRP', 'LTC', 'BCH', 'EOS', 'TRX', 'XLM', 'ATOM', 'VET', 'FIL', 'THETA'
        ]

        popular_tokens = []
        for symbol in popular_symbols[:limit]:
            if symbol in self.token_addresses:
                popular_tokens.append({
                    "symbol": symbol,
                    "address": self.token_addresses[symbol]
                })

        return popular_tokens

    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about the token cache"""
        try:
            if self._token_cache_file.exists():
                with open(self._token_cache_file, 'r') as f:
                    cache_data = json.load(f)

                cache_time = datetime.fromisoformat(cache_data.get('timestamp', '2000-01-01'))
                age_hours = (datetime.now() - cache_time).total_seconds() / 3600

                return {
                    "cache_exists": True,
                    "cache_timestamp": cache_data.get('timestamp'),
                    "cache_age_hours": round(age_hours, 2),
                    "total_tokens": cache_data.get('total_tokens', 0),
                    "chain_id": cache_data.get('chain_id'),
                    "expires_in_hours": max(0, self._cache_expiry_hours - age_hours),
                    "is_expired": age_hours >= self._cache_expiry_hours
                }
            else:
                return {
                    "cache_exists": False,
                    "total_tokens": len(self.token_addresses),
                    "using_fallback": True
                }

        except Exception as e:
            return {"error": str(e)}

    def _check_configuration(self, require_wallet: bool = True) -> bool:
        """Check if the service is properly configured"""
        if not self.api_key:
            raise ValueError("1inch API key not configured")

        if require_wallet:
            if not self.wallet_address:
                raise ValueError("Wallet address not configured")
            if not self.private_key:
                raise ValueError("Private key not configured")
            if not self.web3:
                raise ValueError("Web3 not initialized")

        return True

    def api_request_url(self, method_name: str, query_params: Dict[str, Any]) -> str:
        """Construct full API request URL"""
        params_str = '&'.join([f'{key}={value}' for key, value in query_params.items()])
        return f"{self.api_base_url}{method_name}?{params_str}"

    async def check_allowance(self, token_address: str, wallet_address: str = None) -> int:
        """Check token allowance for 1inch router"""
        try:
            self._check_configuration(require_wallet=True)

            if not wallet_address:
                wallet_address = self.wallet_address

            url = self.api_request_url("/approve/allowance", {
                "tokenAddress": token_address,
                "walletAddress": wallet_address
            })

            response = requests.get(url, headers=self.headers)
            response.raise_for_status()

            data = response.json()
            allowance = int(data.get("allowance", 0))

            logger.info(f"Token allowance for {token_address}: {allowance}")
            return allowance

        except Exception as e:
            logger.error(f"Error checking allowance: {str(e)}")
            return 0

    async def build_approve_transaction(self, token_address: str, amount: Optional[str] = None) -> Dict[str, Any]:
        """Build approval transaction for token"""
        try:
            params = {"tokenAddress": token_address}
            if amount:
                params["amount"] = amount

            url = self.api_request_url("/approve/transaction", params)

            response = requests.get(url, headers=self.headers)
            response.raise_for_status()

            transaction = response.json()

            # Estimate gas limit
            gas_limit = self.web3.eth.estimate_gas({
                **transaction,
                'from': self.wallet_address
            })

            transaction['gas'] = gas_limit
            transaction['gasPrice'] = self.web3.eth.gas_price

            logger.info(f"Built approve transaction for {token_address}")
            return transaction

        except Exception as e:
            logger.error(f"Error building approve transaction: {str(e)}")
            raise

    async def build_swap_transaction(self, swap_params: Dict[str, Any]) -> Dict[str, Any]:
        """Build swap transaction"""
        try:
            url = self.api_request_url("/swap", swap_params)

            response = requests.get(url, headers=self.headers)
            response.raise_for_status()

            data = response.json()
            transaction = data.get("tx")

            if not transaction:
                raise ValueError("No transaction data received from 1inch API")

            logger.info(f"Built swap transaction: {swap_params['src']} -> {swap_params['dst']}")
            return transaction

        except Exception as e:
            logger.error(f"Error building swap transaction: {str(e)}")
            raise

    async def broadcast_raw_transaction(self, raw_transaction: str) -> str:
        """Broadcast raw transaction to the network"""
        try:
            payload = {"rawTransaction": raw_transaction}

            response = requests.post(
                self.broadcast_api_url,
                json=payload,
                headers=self.headers
            )
            response.raise_for_status()

            data = response.json()
            tx_hash = data.get("transactionHash")

            if not tx_hash:
                raise ValueError("No transaction hash received")

            logger.info(f"Transaction broadcasted: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Error broadcasting transaction: {str(e)}")
            raise

    async def sign_and_send_transaction(self, transaction: Dict[str, Any]) -> str:
        """Sign and send transaction"""
        try:
            # Add nonce if not present
            if 'nonce' not in transaction:
                transaction['nonce'] = self.web3.eth.get_transaction_count(self.wallet_address)

            # Sign transaction
            signed_txn = self.web3.eth.account.sign_transaction(transaction, self.private_key)

            # Broadcast transaction
            tx_hash = await self.broadcast_raw_transaction(signed_txn.rawTransaction.hex())

            logger.info(f"Transaction signed and sent: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Error signing and sending transaction: {str(e)}")
            raise

    async def approve_token(self, token_address: str, amount: Optional[str] = None) -> str:
        """Approve token for trading with 1inch router"""
        try:
            # Check current allowance
            current_allowance = await self.check_allowance(token_address)

            if amount and int(amount) <= current_allowance:
                logger.info(f"Token already has sufficient allowance: {current_allowance}")
                return "sufficient_allowance"

            # Build approval transaction
            approve_tx = await self.build_approve_transaction(token_address, amount)

            # Sign and send transaction
            tx_hash = await self.sign_and_send_transaction(approve_tx)

            logger.info(f"Approval transaction sent: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Error approving token: {str(e)}")
            raise

    async def execute_swap(self,
                          src_token: str,
                          dst_token: str,
                          amount: str,
                          slippage: float = 1.0,
                          from_address: str = None) -> Dict[str, Any]:
        """Execute token swap"""
        try:
            self._check_configuration(require_wallet=True)  # Swap needs full configuration

            if not from_address:
                from_address = self.wallet_address

            # Prepare swap parameters
            swap_params = {
                "src": src_token,
                "dst": dst_token,
                "amount": amount,
                "from": from_address,
                "slippage": slippage,
                "disableEstimate": False,
                "allowPartialFill": False
            }

            # Check allowance first
            allowance = await self.check_allowance(src_token, from_address)
            if int(amount) > allowance:
                logger.info("Insufficient allowance, approving token...")
                approve_tx_hash = await self.approve_token(src_token, amount)

                if approve_tx_hash != "sufficient_allowance":
                    # Wait for approval transaction to be mined
                    logger.info("Waiting for approval transaction to be mined...")
                    await asyncio.sleep(10)  # Wait 10 seconds

            # Build swap transaction
            swap_tx = await self.build_swap_transaction(swap_params)

            # Sign and send swap transaction
            swap_tx_hash = await self.sign_and_send_transaction(swap_tx)

            result = {
                "success": True,
                "swap_tx_hash": swap_tx_hash,
                "src_token": src_token,
                "dst_token": dst_token,
                "amount": amount,
                "slippage": slippage,
                "timestamp": datetime.now().isoformat()
            }

            logger.info(f"Swap executed successfully: {result}")
            return result

        except Exception as e:
            logger.error(f"Error executing swap: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def get_quote(self,
                       src_token: str,
                       dst_token: str,
                       amount: str) -> Dict[str, Any]:
        """Get swap quote without executing"""
        try:
            self._check_configuration(require_wallet=False)  # Quote doesn't need wallet

            url = self.api_request_url("/quote", {
                "src": src_token,
                "dst": dst_token,
                "amount": amount
            })

            response = requests.get(url, headers=self.headers)
            response.raise_for_status()

            quote_data = response.json()

            logger.info(f"Quote received: {amount} {src_token} -> {quote_data.get('dstAmount', 0)} {dst_token}")
            return quote_data

        except Exception as e:
            logger.error(f"Error getting quote: {str(e)}")
            raise

    def get_token_address(self, symbol: str) -> str:
        """Get token address by symbol"""
        return self.token_addresses.get(symbol.upper(), symbol)

    async def swap_crypto_to_stable(self,
                                   crypto_symbol: str,
                                   stable_symbol: str,
                                   amount: str,
                                   slippage: float = 1.0) -> Dict[str, Any]:
        """Swap crypto token to stablecoin"""
        try:
            src_token = self.get_token_address(crypto_symbol)
            dst_token = self.get_token_address(stable_symbol)

            result = await self.execute_swap(src_token, dst_token, amount, slippage)

            logger.info(f"Crypto to stable swap: {crypto_symbol} -> {stable_symbol}")
            return result

        except Exception as e:
            logger.error(f"Error in crypto to stable swap: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def swap_stable_to_crypto(self,
                                   stable_symbol: str,
                                   crypto_symbol: str,
                                   amount: str,
                                   slippage: float = 1.0) -> Dict[str, Any]:
        """Swap stablecoin to crypto token"""
        try:
            src_token = self.get_token_address(stable_symbol)
            dst_token = self.get_token_address(crypto_symbol)

            result = await self.execute_swap(src_token, dst_token, amount, slippage)

            logger.info(f"Stable to crypto swap: {stable_symbol} -> {crypto_symbol}")
            return result

        except Exception as e:
            logger.error(f"Error in stable to crypto swap: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

# Create singleton instance
oneinch_service = OneInchService()
