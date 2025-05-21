import os
from dotenv import load_dotenv
import httpx
from typing import Optional, Dict, Any, Callable
from functools import wraps

# Load environment variables
load_dotenv()

# Get API key from environment variables
ONEINCH_API_KEY = os.getenv("ONEINCH_API_KEY", "")

if not ONEINCH_API_KEY:
    print("Warning: 1INCH_API_KEY not found in environment variables")


class OneInchClient:
    """Client for making authenticated requests to the 1inch API"""

    BASE_URL = "https://api.1inch.dev"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ONEINCH_API_KEY
        self.headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make an authenticated GET request to the 1inch API

        Args:
            endpoint: API endpoint (e.g., "/swap/v5.2/1/tokens")
            params: Optional query parameters

        Returns:
            JSON response as a dictionary
        """
        url = f"{self.BASE_URL}{endpoint}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()

    async def post(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make an authenticated POST request to the 1inch API

        Args:
            endpoint: API endpoint
            json_data: JSON data to send in the request body

        Returns:
            JSON response as a dictionary
        """
        url = f"{self.BASE_URL}{endpoint}"

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self.headers, json=json_data)
            response.raise_for_status()
            return response.json()


def with_1inch_client(func: Callable) -> Callable:
    """
    Decorator to inject a 1inch client into the wrapped function

    Usage:
        @with_1inch_client
        async def my_function(client: OneInchClient, *args, **kwargs):
            # Use client to make API calls
            data = await client.get("/some/endpoint")
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        client = OneInchClient()
        return await func(client, *args, **kwargs)
    return wrapper

one_inch_client = OneInchClient()
