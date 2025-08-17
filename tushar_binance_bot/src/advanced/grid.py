import argparse
import os
import sys
from typing import List

# Ensure parent directory (src) is on path when running as script
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from binance.client import Client

from config import get_client, get_exchange_info
from utils import log_info, log_error, validate_order_inputs, safe_api_call, is_tick_size_compliant


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Binance Futures Grid Trading (static placement)")
	parser.add_argument("symbol", help="Trading symbol (e.g., BTCUSDT)")
	parser.add_argument("lower", type=float, help="Lower bound price")
	parser.add_argument("upper", type=float, help="Upper bound price")
	parser.add_argument("levels", type=int, help="Number of grid levels")
	parser.add_argument("quantity", type=float, help="Order quantity per level")
	return parser.parse_args()


def linspace(start: float, stop: float, num: int) -> List[float]:
	if num == 1:
		return [start]
	step = (stop - start) / (num - 1)
	return [start + i * step for i in range(num)]


def main():
	args = parse_args()
	client = get_client()
	exchange_info = get_exchange_info()
	valid, msg, filters = validate_order_inputs(exchange_info, args.symbol, args.quantity)
	if not valid:
		log_error(msg, action="VALIDATION")
		raise SystemExit(msg)
	if args.upper <= args.lower:
		raise SystemExit("upper must be greater than lower")
	if args.levels < 2:
		raise SystemExit("levels must be >= 2")

	# Current price to decide buy/sell sides
	ticker = safe_api_call(client.futures_symbol_ticker, action="TICKER", symbol=args.symbol.upper())
	current_price = float(ticker.get("price", 0.0))
	levels = linspace(args.lower, args.upper, args.levels)
	placed = 0

	for price in levels:
		if not is_tick_size_compliant(price, filters.tick_size):
			continue
		if price < current_price:
			# Place buy limit below market
			params = {
				"symbol": args.symbol.upper(),
				"side": "BUY",
				"type": "LIMIT",
				"timeInForce": "GTC",
				"quantity": args.quantity,
				"price": price,
			}
			log_info(f"Grid BUY {args.quantity} {args.symbol} @ {price}", action="GRID")
			safe_api_call(client.futures_create_order, action="GRID_BUY", **params)
			placed += 1
		elif price > current_price:
			# Place sell limit above market
			params = {
				"symbol": args.symbol.upper(),
				"side": "SELL",
				"type": "LIMIT",
				"timeInForce": "GTC",
				"quantity": args.quantity,
				"price": price,
			}
			log_info(f"Grid SELL {args.quantity} {args.symbol} @ {price}", action="GRID")
			safe_api_call(client.futures_create_order, action="GRID_SELL", **params)
			placed += 1

	log_info(f"Grid placement finished. Orders placed: {placed}", action="GRID")


if __name__ == "__main__":
	main()


