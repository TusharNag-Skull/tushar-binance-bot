import argparse
import math
import os
import sys
import time
from typing import Dict, Any

# Ensure parent directory (src) is on path when running as script
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL

from config import get_client, get_exchange_info, ORDER_SIDE
from utils import log_info, log_error, validate_order_inputs, safe_api_call


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Binance Futures TWAP Market Execution")
	parser.add_argument("symbol", help="Trading symbol (e.g., BTCUSDT)")
	parser.add_argument("side", choices=["BUY", "SELL"], help="Order side")
	parser.add_argument("total_quantity", type=float, help="Total quantity to execute")
	parser.add_argument("duration_seconds", type=int, help="Total time to execute (seconds)")
	parser.add_argument("slices", type=int, help="Number of slices (orders)")
	return parser.parse_args()


def place_market(client: Client, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
	return safe_api_call(
		client.futures_create_order,
		action="TWAP_MARKET",
		symbol=symbol.upper(),
		side=side,
		type="MARKET",
		quantity=quantity,
	)


def main():
	args = parse_args()
	client = get_client()
	exchange_info = get_exchange_info()
	valid, msg, filters = validate_order_inputs(exchange_info, args.symbol, args.total_quantity)
	if not valid or not filters:
		log_error(msg, action="VALIDATION")
		raise SystemExit(msg)
	if args.slices <= 0 or args.duration_seconds <= 0:
		msg = "slices and duration_seconds must be positive."
		log_error(msg, action="VALIDATION")
		raise SystemExit(msg)

	interval = args.duration_seconds / args.slices
	per_slice_raw = args.total_quantity / args.slices
	# Adjust per-slice to step size by flooring to nearest step and quantize to symbol precision
	step = filters.step_size if filters.step_size > 0 else 0.0
	if step > 0:
		steps_count = math.floor(per_slice_raw / step)
		per_slice = steps_count * step
		# Round to 8 decimals to avoid float artifacts
		per_slice = float(f"{per_slice:.8f}")
	else:
		per_slice = float(f"{per_slice_raw:.8f}")

	if per_slice <= 0:
		raise SystemExit("Per-slice quantity is below step size; reduce slices or increase total_quantity.")

	remaining = args.total_quantity
	for i in range(args.slices):
		qty = per_slice if remaining >= per_slice else float(f"{remaining:.8f}")
		# Ensure qty aligns with step size
		if step > 0:
			steps_count = math.floor(qty / step)
			qty = float(f"{(steps_count * step):.8f}")
		if qty <= 0:
			break
		log_info(f"TWAP slice {i+1}/{args.slices}: {args.side} {qty} {args.symbol}", action="TWAP")
		place_market(client, args.symbol, args.side, qty)
		remaining = max(0.0, remaining - qty)
		if i < args.slices - 1:
			time.sleep(interval)
	log_info("TWAP execution finished", action="TWAP")


if __name__ == "__main__":
	main()


