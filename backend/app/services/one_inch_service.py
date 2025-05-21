from typing import Dict, List, Optional, Any
from app.middleware.one_inch_token_handler import OneInchClient
from app.core.logger import logger

class OneInchService:
    def __init__(self):
        self.client = OneInchClient()
        self.logger = logger

    async def get_tokens(self, chain_id: int) -> Dict[str, Any]:
        """
        Get all tokens supported by 1inch on a specific chain

        Args:
            chain_id: Blockchain ID (e.g., 1 for Ethereum)

        Returns:
            Dictionary of token data
        """
        try:
            self.logger.info(f"Fetching tokens for chain {chain_id}")
            tokens = await self.client.get(f"/swap/v5.2/{chain_id}/tokens")
            self.logger.info(f"Found {len(tokens.get('tokens', {}))} tokens on chain {chain_id}")
            return tokens
        except Exception as e:
            self.logger.error(f"Error fetching tokens for chain {chain_id}: {str(e)}")
            raise

    async def get_token_by_address(self, chain_id: int, token_address: str) -> Optional[Dict[str, Any]]:
        """
        Get token information by its address

        Args:
            chain_id: Blockchain ID (e.g., 1 for Ethereum)
            token_address: Token contract address

        Returns:
            Token information or None if not found
        """
        try:
            self.logger.info(f"Fetching token {token_address} on chain {chain_id}")
            tokens = await self.client.get(f"/swap/v5.2/{chain_id}/tokens")
            token = tokens.get('tokens', {}).get(token_address)

            if token:
                self.logger.info(f"Found token {token.get('symbol')} at {token_address}")
                return {"address": token_address, **token}
            else:
                self.logger.warning(f"Token {token_address} not found on chain {chain_id}")
                return None
        except Exception as e:
            self.logger.error(f"Error fetching token {token_address} on chain {chain_id}: {str(e)}")
            raise

    async def get_quote(self, chain_id: int, from_token: str, to_token: str, amount: str) -> Dict[str, Any]:
        """
        Get a quote for swapping tokens

        Args:
            chain_id: Blockchain ID (e.g., 1 for Ethereum)
            from_token: Source token address
            to_token: Destination token address
            amount: Amount in wei (base units)

        Returns:
            Quote data
        """
        try:
            self.logger.info(f"Getting quote for {amount} {from_token} to {to_token} on chain {chain_id}")
            params = {
                "fromTokenAddress": from_token,
                "toTokenAddress": to_token,
                "amount": amount
            }

            quote = await self.client.get(f"/swap/v5.2/{chain_id}/quote", params)

            self.logger.info(
                f"Quote: {amount} {quote.get('fromToken', {}).get('symbol')} → "
                f"{quote.get('toTokenAmount')} {quote.get('toToken', {}).get('symbol')}"
            )

            return quote
        except Exception as e:
            self.logger.error(f"Error getting quote on chain {chain_id}: {str(e)}")
            raise

    async def get_swap(
        self,
        chain_id: int,
        from_token: str,
        to_token: str,
        amount: str,
        from_address: str,
        slippage: float = 1.0
    ) -> Dict[str, Any]:
        """
        Get swap transaction data

        Args:
            chain_id: Blockchain ID (e.g., 1 for Ethereum)
            from_token: Source token address
            to_token: Destination token address
            amount: Amount in wei (base units)
            from_address: Sender address
            slippage: Maximum acceptable slippage in percentage (default: 1.0)

        Returns:
            Swap transaction data
        """
        try:
            self.logger.info(f"Getting swap data for {amount} {from_token} to {to_token} on chain {chain_id}")
            params = {
                "fromTokenAddress": from_token,
                "toTokenAddress": to_token,
                "amount": amount,
                "fromAddress": from_address,
                "slippage": str(slippage)
            }

            swap_data = await self.client.get(f"/swap/v5.2/{chain_id}/swap", params)

            self.logger.info(
                f"Swap data generated for {amount} {swap_data.get('fromToken', {}).get('symbol')} → "
                f"{swap_data.get('toTokenAmount')} {swap_data.get('toToken', {}).get('symbol')}"
            )

            return swap_data
        except Exception as e:
            self.logger.error(f"Error getting swap data on chain {chain_id}: {str(e)}")
            raise

    async def get_protocols(self, chain_id: int) -> Dict[str, Any]:
        """
        Get protocols supported by 1inch on a specific chain

        Args:
            chain_id: Blockchain ID (e.g., 1 for Ethereum)

        Returns:
            Protocols data
        """
        try:
            self.logger.info(f"Fetching protocols for chain {chain_id}")
            protocols = await self.client.get(f"/swap/v5.2/{chain_id}/liquidity-sources")

            self.logger.info(f"Found {len(protocols.get('protocols', []))} protocols on chain {chain_id}")
            return protocols
        except Exception as e:
            self.logger.error(f"Error fetching protocols for chain {chain_id}: {str(e)}")
            raise

    async def get_healthcheck(self, chain_id: int) -> Dict[str, Any]:
        """
        Check the health of the 1inch API for a specific chain

        Args:
            chain_id: Blockchain ID (e.g., 1 for Ethereum)

        Returns:
            Health status
        """
        try:
            self.logger.info(f"Checking API health for chain {chain_id}")
            health = await self.client.get(f"/swap/v5.2/{chain_id}/healthcheck")

            status = "healthy" if health.get("status") == "success" else "unhealthy"
            self.logger.info(f"1inch API for chain {chain_id} is {status}")

            return health
        except Exception as e:
            self.logger.error(f"Error checking API health for chain {chain_id}: {str(e)}")
            raise

# Create a singleton instance
one_inch_service = OneInchService()
