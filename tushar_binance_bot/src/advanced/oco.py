import argparse
import os
import sys
import time
from typing import Dict, Any

# Ensure parent directory (src) is on path when running as script
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from binance.client import Client

from config import get_client, get_exchange_info, ORDER_SIDE
from utils import log_info, log_error, validate_order_inputs, safe_api_call


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Binance Futures OCO-like (TP/SL) manager")
	parser.add_argument("symbol", help="Trading symbol (e.g., BTCUSDT)")
	parser.add_argument("side", choices=["BUY", "SELL"], help="Side to close (opposite of your position)")
	parser.add_argument("quantity", type=float, help="Quantity to close")
	parser.add_argument("take_profit_price", type=float, help="Take-profit price")
	parser.add_argument("stop_loss_price", type=float, help="Stop-loss trigger price (market)")
	parser.add_argument("--poll", type=int, default=5, help="Polling interval seconds (default 5)")
	parser.add_argument("--max-wait", type=int, default=600, help="Max seconds to monitor before exit (default 600)")
	return parser.parse_args()


def place_tp_sl(client: Client, symbol: str, side: str, qty: float, tp_price: float, sl_price: float) -> Dict[str, int]:
	# Take profit as regular LIMIT order (posts above/below market), Stop loss as STOP_MARKET on MARK_PRICE
	orders: Dict[str, int] = {}
	log_info(f"Placing TP LIMIT {side} {qty} {symbol} @ {tp_price}", action="ORDER")
	tp = safe_api_call(
		client.futures_create_order,
		action="TP_ORDER",
		symbol=symbol.upper(),
		side=side,
		type="LIMIT",
		quantity=qty,
		price=tp_price,
		timeInForce="GTC",
		reduceOnly=True,
	)
	orders["tp"] = tp.get("orderId")

	log_info(f"Placing SL STOP_MARKET {side} {qty} {symbol} @ {sl_price}", action="ORDER")
	sl = safe_api_call(
		client.futures_create_order,
		action="SL_ORDER",
		symbol=symbol.upper(),
		side=side,
		type="STOP_MARKET",
		quantity=qty,
		stopPrice=sl_price,
		reduceOnly=True,
		workingType="MARK_PRICE",
	)
	orders["sl"] = sl.get("orderId")
	log_info(f"TP/SL orders placed tpId={orders['tp']} slId={orders['sl']}", action="ORDER")
	return orders


def get_status(client: Client, symbol: str, order_id: int) -> str:
	order = safe_api_call(client.futures_get_order, action="ORDER_STATUS", symbol=symbol.upper(), orderId=order_id)
	return str(order.get("status", ""))


def cancel_order(client: Client, symbol: str, order_id: int) -> None:
	safe_api_call(client.futures_cancel_order, action="CANCEL_ORDER", symbol=symbol.upper(), orderId=order_id)
	log_info(f"Canceled orderId={order_id}", action="CANCEL")


def main():
	args = parse_args()
	client = get_client()
	exchange_info = get_exchange_info()
	# Validate symbol and quantity only; prices are validated to be positive
	valid, msg, _filters = validate_order_inputs(exchange_info, args.symbol, args.quantity, None)
	if not valid:
		log_error(msg, action="VALIDATION")
		raise SystemExit(msg)
	if args.take_profit_price <= 0 or args.stop_loss_price <= 0:
		msg = "Prices must be positive."
		log_error(msg, action="VALIDATION")
		raise SystemExit(msg)

	try:
		orders = place_tp_sl(client, args.symbol, args.side, args.quantity, args.take_profit_price, args.stop_loss_price)
		start = time.time()
		while time.time() - start < args.max_wait:
			status_tp = get_status(client, args.symbol, orders["tp"]) if orders.get("tp") else ""
			status_sl = get_status(client, args.symbol, orders["sl"]) if orders.get("sl") else ""
			if status_tp == "FILLED" and orders.get("sl"):
				cancel_order(client, args.symbol, orders["sl"])
				break
			if status_sl == "FILLED" and orders.get("tp"):
				cancel_order(client, args.symbol, orders["tp"])
				break
			time.sleep(args.poll)
		log_info("OCO monitoring finished", action="EXECUTION")
	except Exception as e:
		raise SystemExit(str(e))


if __name__ == "__main__":
	main()


