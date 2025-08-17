import argparse
import os
import sys
from typing import Dict, Any

# Ensure parent directory (src) is on path when running as script
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from binance.client import Client

from config import get_client, get_exchange_info, DEFAULT_TIME_IN_FORCE, ORDER_SIDE
from utils import log_info, log_error, validate_order_inputs, safe_api_call


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Binance Futures Stop-Limit Order")
	parser.add_argument("symbol", help="Trading symbol (e.g., BTCUSDT)")
	parser.add_argument("side", choices=["BUY", "SELL"], help="Order side")
	parser.add_argument("quantity", type=float, help="Order quantity")
	parser.add_argument("stop_price", type=float, help="Trigger price")
	parser.add_argument("limit_price", type=float, help="Limit price once triggered")
	return parser.parse_args()


def place_stop_limit_order(client: Client, symbol: str, side: str, quantity: float, stop_price: float, limit_price: float) -> Dict[str, Any]:
	params = {
		"symbol": symbol.upper(),
		"side": side,
		"type": "STOP",
		"timeInForce": DEFAULT_TIME_IN_FORCE,
		"quantity": quantity,
		"price": limit_price,
		"stopPrice": stop_price,
	}
	log_info(f"Placing STOP-LIMIT {side} {quantity} {symbol} stop={stop_price} limit={limit_price}", action="ORDER")
	order = safe_api_call(client.futures_create_order, action="STOP_LIMIT_ORDER", **params)
	log_info(f"Order placed: orderId={order.get('orderId')} status={order.get('status')}", action="ORDER")
	return order


def main():
	args = parse_args()
	client = get_client()
	exchange_info = get_exchange_info()
	valid, msg, _filters = validate_order_inputs(exchange_info, args.symbol, args.quantity, args.limit_price)
	if not valid:
		log_error(msg, action="VALIDATION")
		raise SystemExit(msg)
	if args.stop_price <= 0:
		log_error("Stop price must be positive.", action="VALIDATION")
		raise SystemExit("Stop price must be positive.")
	try:
		place_stop_limit_order(client, args.symbol, args.side, args.quantity, args.stop_price, args.limit_price)
	except Exception as e:
		raise SystemExit(str(e))


if __name__ == "__main__":
	main()


