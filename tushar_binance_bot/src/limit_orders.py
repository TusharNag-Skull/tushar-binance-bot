import argparse
from typing import Dict, Any

from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL, TIME_IN_FORCE_GTC

from config import get_client, get_exchange_info, DEFAULT_TIME_IN_FORCE, ORDER_SIDE
from utils import log_info, log_error, validate_order_inputs, safe_api_call


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Binance Futures Limit Order")
	parser.add_argument("symbol", help="Trading symbol (e.g., BTCUSDT)")
	parser.add_argument("side", choices=["BUY", "SELL"], help="Order side")
	parser.add_argument("quantity", type=float, help="Order quantity")
	parser.add_argument("price", type=float, help="Limit price")
	return parser.parse_args()


def place_limit_order(client: Client, symbol: str, side: str, quantity: float, price: float) -> Dict[str, Any]:
	params = {
		"symbol": symbol.upper(),
		"side": SIDE_BUY if side == ORDER_SIDE["BUY"] else SIDE_SELL,
		"type": "LIMIT",
		"timeInForce": DEFAULT_TIME_IN_FORCE or TIME_IN_FORCE_GTC,
		"quantity": quantity,
		"price": price,
	}
	log_info(f"Placing LIMIT {side} {quantity} {symbol} @ {price}", action="ORDER")
	order = safe_api_call(client.futures_create_order, action="LIMIT_ORDER", **params)
	log_info(f"Order placed: orderId={order.get('orderId')} status={order.get('status')}", action="ORDER")
	return order


def check_order_status(client: Client, symbol: str, order_id: int) -> Dict[str, Any]:
	order = safe_api_call(client.futures_get_order, action="ORDER_STATUS", symbol=symbol.upper(), orderId=order_id)
	log_info(f"Order status: orderId={order.get('orderId')} status={order.get('status')} executedQty={order.get('executedQty')}", action="EXECUTION")
	return order


def main():
	args = parse_args()
	client = get_client()
	exchange_info = get_exchange_info()
	valid, msg, _filters = validate_order_inputs(exchange_info, args.symbol, args.quantity, args.price)
	if not valid:
		log_error(msg, action="VALIDATION")
		raise SystemExit(msg)
	try:
		order = place_limit_order(client, args.symbol, args.side, args.quantity, args.price)
		check_order_status(client, args.symbol, order.get("orderId"))
	except Exception as e:
		raise SystemExit(str(e))


if __name__ == "__main__":
	main()


