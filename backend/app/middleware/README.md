# 1inch API Integration

This directory contains middleware for interacting with the 1inch API.

## Setup

1. Get an API key from the [1inch Developer Portal](https://portal.1inch.dev)
2. Add your API key to your .env file:
   ```
   ONEINCH_API_KEY=your_api_key_here
   ```

## Usage

### Basic Usage

```python
from app.middleware.1inch_token_handler import OneInchClient

async def get_tokens():
    client = OneInchClient()
    tokens = await client.get("/swap/v5.2/1/tokens")
    return tokens
```

### Using the Decorator

```python
from app.middleware.1inch_token_handler import with_1inch_client, OneInchClient

@with_1inch_client
async def get_quote(client: OneInchClient, from_token: str, to_token: str, amount: str):
    params = {
        "fromTokenAddress": from_token,
        "toTokenAddress": to_token,
        "amount": amount
    }

    quote = await client.get(f"/swap/v5.2/1/quote", params)
    return quote
```

## API Endpoints

The 1inch API has various endpoints for interacting with the 1inch protocol:

- `/swap/v5.2/{chainId}/tokens` - Get supported tokens
- `/swap/v5.2/{chainId}/quote` - Get swap quote
- `/swap/v5.2/{chainId}/swap` - Execute a swap

For more information, refer to the [1inch API documentation](https://portal.1inch.dev/documentation/swap).

## Authentication

The client automatically adds the Authorization header with your API key:

```
Authorization: Bearer YOUR_API_KEY
```

This is required for all 1inch API endpoints.
