import asyncio
from app.middleware.one_inch_token_handler import OneInchClient, with_1inch_client


# Example using the client directly
async def get_tokens_direct():
    """Example: Get tokens directly with the OneInchClient"""
    client = OneInchClient()

    try:
        # Get Ethereum (chain ID 1) tokens
        tokens = await client.get("/swap/v5.2/1/tokens")
        print(f"Found {len(tokens.get('tokens', {}))} tokens on Ethereum")

        # Print the first 3 tokens for example
        for i, (token_address, token_info) in enumerate(list(tokens.get('tokens', {}).items())[:3]):
            print(f"Token {i+1}: {token_info.get('symbol')} - {token_info.get('name')}")

        return tokens
    except Exception as e:
        print(f"Error fetching tokens: {e}")
        return None


# Example using the decorator approach
@with_1inch_client
async def get_token_by_address(client: OneInchClient, chain_id: int, token_address: str):
    """
    Example: Get a specific token by its address

    Args:
        client: Injected OneInchClient by the decorator
        chain_id: Blockchain ID (e.g., 1 for Ethereum)
        token_address: The token's contract address
    """
    try:
        tokens = await client.get(f"/swap/v5.2/{chain_id}/tokens")
        token = tokens.get('tokens', {}).get(token_address)

        if token:
            print(f"Token found: {token.get('symbol')} - {token.get('name')}")
            return token
        else:
            print(f"Token not found with address {token_address}")
            return None
    except Exception as e:
        print(f"Error fetching token: {e}")
        return None


# Example of getting the best swap quote
@with_1inch_client
async def get_quote(client: OneInchClient, chain_id: int, from_token: str, to_token: str, amount: str):
    """
    Example: Get a quote for swapping tokens

    Args:
        client: Injected OneInchClient by the decorator
        chain_id: Blockchain ID (e.g., 1 for Ethereum)
        from_token: Source token address
        to_token: Destination token address
        amount: Amount in wei (base units)
    """
    try:
        params = {
            "fromTokenAddress": from_token,
            "toTokenAddress": to_token,
            "amount": amount
        }

        quote = await client.get(f"/swap/v5.2/{chain_id}/quote", params)
        print(f"Quote: {amount} {quote.get('fromToken', {}).get('symbol')} → {quote.get('toTokenAmount')} {quote.get('toToken', {}).get('symbol')}")
        return quote
    except Exception as e:
        print(f"Error getting quote: {e}")
        return None


# Example runner function
async def run_examples():
    # First, make sure to set your 1INCH_API_KEY in the .env file!

    # Example 1: Get all tokens on Ethereum
    await get_tokens_direct()

    # Example 2: Get USDC token info
    # USDC token address on Ethereum
    usdc_address = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    await get_token_by_address(chain_id=1, token_address=usdc_address)

    # Example 3: Get a quote for swapping ETH to USDC
    # ETH token address (in 1inch, 0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE represents native ETH)
    eth_address = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"

    # Amount in wei (1 ETH = 10^18 wei)
    amount = "1000000000000000000"  # 1 ETH

    await get_quote(chain_id=1, from_token=eth_address, to_token=usdc_address, amount=amount)


# To run the examples
if __name__ == "__main__":
    asyncio.run(run_examples())
