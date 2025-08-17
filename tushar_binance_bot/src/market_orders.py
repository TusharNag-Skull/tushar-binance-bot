import argparse
from typing import Dict, Any

from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL

from config import get_client, get_exchange_info, ORDER_SIDE
from utils import log_info, log_error, validate_order_inputs, safe_api_call


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Binance Futures Market Order")
	parser.add_argument("symbol", help="Trading symbol (e.g., BTCUSDT)")
	parser.add_argument("side", choices=["BUY", "SELL"], help="Order side")
	parser.add_argument("quantity", type=float, help="Order quantity")
	return parser.parse_args()


def place_market_order(client: Client, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
	params = {
		"symbol": symbol.upper(),
		"side": SIDE_BUY if side == ORDER_SIDE["BUY"] else SIDE_SELL,
		"type": "MARKET",
		"quantity": quantity,
	}
	log_info(f"Placing MARKET {side} {quantity} {symbol}", action="ORDER")
	order = safe_api_call(client.futures_create_order, action="MARKET_ORDER", **params)
	log_info(f"Order placed: orderId={order.get('orderId')} status={order.get('status')}", action="ORDER")
	return order


def main():
	args = parse_args()
	client = get_client()
	exchange_info = get_exchange_info()
	valid, msg, _filters = validate_order_inputs(exchange_info, args.symbol, args.quantity)
	if not valid:
		log_error(msg, action="VALIDATION")
		raise SystemExit(msg)
	try:
		place_market_order(client, args.symbol, args.side, args.quantity)
	except Exception as e:
		raise SystemExit(str(e))


if __name__ == "__main__":
	main()


