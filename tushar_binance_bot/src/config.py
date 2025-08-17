import os
from typing import Dict, Any

from dotenv import load_dotenv
from binance.client import Client


# Load environment variables from .env if present
load_dotenv()


BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY: str = os.getenv("BINANCE_SECRET_KEY", "")
USE_TESTNET_ENV: str = os.getenv("USE_TESTNET", "True").strip().lower()
USE_TESTNET: bool = USE_TESTNET_ENV in {"1", "true", "yes", "y"}


# Constants
ORDER_SIDE = {"BUY": "BUY", "SELL": "SELL"}
ORDER_TYPE = {"MARKET": "MARKET", "LIMIT": "LIMIT", "STOP": "STOP", "STOP_MARKET": "STOP_MARKET"}
TIME_IN_FORCE = {"GTC": "GTC", "IOC": "IOC", "FOK": "FOK"}
DEFAULT_TIME_IN_FORCE: str = TIME_IN_FORCE["GTC"]


_client: Client | None = None


def get_client() -> Client:

	global _client
	if _client is not None:
		return _client

	if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
		raise RuntimeError("BINANCE_API_KEY or BINANCE_SECRET_KEY not set. Create a .env file with credentials.")

	# python-binance Client handles Futures Testnet when testnet=True
	_client = Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_SECRET_KEY, testnet=USE_TESTNET)
	return _client


def get_exchange_info() -> Dict[str, Any]:

	client = get_client()
	return client.futures_exchange_info()


