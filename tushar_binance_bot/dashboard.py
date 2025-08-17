import os
import time
from typing import Dict, Any, List

import streamlit as st

from src.config import get_client, get_exchange_info, USE_TESTNET
from src.utils import validate_order_inputs, safe_api_call


def get_prices(client, symbol: str) -> Dict[str, float]:
	try:
		mark = safe_api_call(client.futures_mark_price, action="MARK_PRICE", symbol=symbol.upper())
		last = safe_api_call(client.futures_symbol_ticker, action="LAST_PRICE", symbol=symbol.upper())
		return {"mark": float(mark.get("markPrice", 0.0)), "last": float(last.get("price", 0.0))}
	except Exception:
		return {"mark": 0.0, "last": 0.0}


def tail_log(path: str, max_lines: int = 200) -> str:
	if not os.path.exists(path):
		return ""
	try:
		with open(path, "r", encoding="utf-8", errors="ignore") as f:
			lines = f.readlines()
			return "".join(lines[-max_lines:])
	except Exception:
		return ""


def fetch_account_info(client) -> Dict[str, Any]:
	info: Dict[str, Any] = {"balances": [], "positions": []}
	try:
		acct = safe_api_call(client.futures_account, action="ACCOUNT")
		info["balances"] = acct.get("assets", [])
		positions = acct.get("positions", [])
		info["positions"] = [p for p in positions if abs(float(p.get("positionAmt", 0))) > 0]
	except Exception:
		pass
	return info


def fetch_open_orders(client, symbol: str) -> List[Dict[str, Any]]:
	try:
		orders = safe_api_call(client.futures_get_open_orders, action="OPEN_ORDERS", symbol=symbol.upper())
		return orders or []
	except Exception:
		return []


def watch_log_and_rerun(path: str, poll_interval: float = 1.0, max_wait: int = 600) -> None:
	last = float(st.session_state.get("log_mtime", 0.0))
	try:
		current = os.path.getmtime(path)
	except OSError:
		current = 0.0
	if last == 0.0:
		st.session_state["log_mtime"] = current
	start = time.time()
	while time.time() - start < max_wait:
		try:
			mtime = os.path.getmtime(path)
		except OSError:
			mtime = 0.0
		if mtime > float(st.session_state.get("log_mtime", 0.0)):
			st.session_state["log_mtime"] = mtime
			st.rerun()
		time.sleep(max(0.1, float(poll_interval)))


def main():
	st.set_page_config(page_title="Binance Futures (Testnet)", layout="wide")
	st.title("Binance Futures (Testnet)")
	st.caption(f"Testnet enabled: {USE_TESTNET}")

	client = get_client()
	exchange_info = get_exchange_info()

	# Sidebar controls
	st.sidebar.header("Controls")
	auto = st.sidebar.checkbox("Auto-refresh logs", value=True)
	interval = st.sidebar.number_input("Interval (s)", min_value=1, max_value=30, value=5, step=1)

	symbol = st.text_input("Symbol", value="BTCUSDT").upper()
	prices = get_prices(client, symbol)

	# Tabs for sections
	trade_tab, adv_tab, acct_tab, logs_tab = st.tabs(["Trading", "Advanced", "Account", "Logs"])

	with trade_tab:
		col_price, col_actions = st.columns([1, 1])
		with col_price:
			st.metric("Mark Price", prices["mark"])
			st.metric("Last Price", prices["last"])
		with col_actions:
			st.subheader("Market Order")
			with st.form("market_form"):
				side = st.selectbox("Side", ["BUY", "SELL"], index=0)
				qty = st.number_input("Quantity", min_value=0.0, step=0.001, value=0.01, format="%f")
				submit_market = st.form_submit_button("Place Market Order")
				if submit_market:
					valid, msg, _ = validate_order_inputs(exchange_info, symbol, float(qty))
					if not valid:
						st.error(msg)
					else:
						try:
							order = safe_api_call(
								client.futures_create_order,
								action="MARKET_ORDER_UI",
								symbol=symbol,
								side=side,
								type="MARKET",
								quantity=float(qty),
							)
							st.success(f"Placed market order: id={order.get('orderId')} status={order.get('status')}")
						except Exception as e:
							st.error(str(e))

			st.subheader("Limit Order")
			with st.form("limit_form"):
				side_l = st.selectbox("Side (Limit)", ["BUY", "SELL"], index=0)
				qty_l = st.number_input("Quantity (Limit)", min_value=0.0, step=0.001, value=0.01, format="%f")
				price_l = st.number_input("Price", min_value=0.0, step=0.1, value=0.0, format="%f")
				submit_limit = st.form_submit_button("Place Limit Order")
				if submit_limit:
					valid, msg, _ = validate_order_inputs(exchange_info, symbol, float(qty_l), float(price_l))
					if not valid:
						st.error(msg)
					else:
						try:
							order = safe_api_call(
								client.futures_create_order,
								action="LIMIT_ORDER_UI",
								symbol=symbol,
								side=side_l,
								type="LIMIT",
								timeInForce="GTC",
								quantity=float(qty_l),
								price=float(price_l),
							)
							st.success(f"Placed limit order: id={order.get('orderId')} status={order.get('status')}")
						except Exception as e:
							st.error(str(e))

	with adv_tab:
		st.subheader("Stop-Limit")
		with st.form("stop_limit_form"):
			side_s = st.selectbox("Side (Stop-Limit)", ["BUY", "SELL"], index=0)
			qty_s = st.number_input("Quantity (SL)", min_value=0.0, step=0.001, value=0.01, format="%f")
			stop_price = st.number_input("Stop Price", min_value=0.0, step=0.1, value=0.0, format="%f")
			limit_price = st.number_input("Limit Price", min_value=0.0, step=0.1, value=0.0, format="%f")
			do_sl = st.form_submit_button("Place Stop-Limit")
			if do_sl:
				ok, msg, _ = validate_order_inputs(exchange_info, symbol, float(qty_s), float(limit_price))
				if not ok or stop_price <= 0:
					st.error(msg or "Stop price must be positive")
				else:
					try:
						order = safe_api_call(
							client.futures_create_order,
							action="STOP_LIMIT_UI",
							symbol=symbol,
							side=side_s,
							type="STOP",
							timeInForce="GTC",
							quantity=float(qty_s),
							price=float(limit_price),
							stopPrice=float(stop_price),
						)
						st.success(f"Stop-limit placed id={order.get('orderId')} status={order.get('status')}")
					except Exception as e:
						st.error(str(e))

		st.subheader("OCO (TP/SL emulation)")
		with st.form("oco_form"):
			side_o = st.selectbox("Side (close)", ["BUY", "SELL"], index=1)
			qty_o = st.number_input("Quantity (OCO)", min_value=0.0, step=0.001, value=0.01, format="%f")
			tp = st.number_input("Take Profit Price", min_value=0.0, step=0.1, value=0.0, format="%f")
			sl = st.number_input("Stop Loss Price", min_value=0.0, step=0.1, value=0.0, format="%f")
			do_oco = st.form_submit_button("Place TP & SL")
			if do_oco:
				if tp <= 0 or sl <= 0:
					st.error("Prices must be positive")
				else:
					try:
						# TP as LIMIT, SL as STOP_MARKET on mark price
						_ = safe_api_call(
							client.futures_create_order,
							action="TP_UI",
							symbol=symbol,
							side=side_o,
							type="LIMIT",
							timeInForce="GTC",
							quantity=float(qty_o),
							price=float(tp),
							reduceOnly=True,
						)
						_ = safe_api_call(
							client.futures_create_order,
							action="SL_UI",
							symbol=symbol,
							side=side_o,
							type="STOP_MARKET",
							quantity=float(qty_o),
							stopPrice=float(sl),
							reduceOnly=True,
							workingType="MARK_PRICE",
						)
						st.success("TP/SL orders placed")
					except Exception as e:
						st.error(str(e))

		st.subheader("TWAP (quick run)")
		with st.form("twap_form"):
			qty_t = st.number_input("Total Quantity", min_value=0.0, step=0.001, value=0.05, format="%f")
			slices = st.number_input("Slices", min_value=1, step=1, value=5)
			do_twap = st.form_submit_button("Execute TWAP")
			if do_twap:
				per = max(0.0, float(qty_t) / int(slices))
				try:
					for _ in range(int(slices)):
						if per <= 0:
							break
						_ = safe_api_call(
							client.futures_create_order,
							action="TWAP_UI",
							symbol=symbol,
							side="BUY",
							type="MARKET",
							quantity=float(per),
						)
					st.success("TWAP submitted (sequential market slices)")
				except Exception as e:
					st.error(str(e))

		st.subheader("Grid (static)")
		with st.form("grid_form"):
			lower = st.number_input("Lower", min_value=0.0, step=0.1, value=0.0, format="%f")
			upper = st.number_input("Upper", min_value=0.0, step=0.1, value=0.0, format="%f")
			levels = st.number_input("Levels", min_value=2, step=1, value=6)
			qty_g = st.number_input("Qty/Level", min_value=0.0, step=0.001, value=0.01, format="%f")
			do_grid = st.form_submit_button("Place Grid")
			if do_grid and upper > lower:
				try:
					cur = get_prices(client, symbol)["mark"]
					step = (float(upper) - float(lower)) / (int(levels) - 1)
					for i in range(int(levels)):
						price = float(lower) + i * step
						if price < cur:
							_ = safe_api_call(client.futures_create_order, action="GRID_BUY_UI", symbol=symbol, side="BUY", type="LIMIT", timeInForce="GTC", quantity=float(qty_g), price=price)
						elif price > cur:
							_ = safe_api_call(client.futures_create_order, action="GRID_SELL_UI", symbol=symbol, side="SELL", type="LIMIT", timeInForce="GTC", quantity=float(qty_g), price=price)
					st.success("Grid orders placed")
				except Exception as e:
					st.error(str(e))

	with acct_tab:
		acct = fetch_account_info(client)
		st.subheader("Open Positions")
		if acct.get("positions"):
			st.dataframe(acct["positions"])
		else:
			st.write("No open positions")

		st.subheader("Open Orders")
		open_orders = fetch_open_orders(client, symbol)
		if open_orders:
			st.dataframe(open_orders)
		else:
			st.write("No open orders")

		st.subheader("Cancel Order")
		with st.form("cancel_form"):
			cancel_id = st.text_input("Order ID")
			do_cancel = st.form_submit_button("Cancel")
			if do_cancel and cancel_id:
				try:
					safe_api_call(client.futures_cancel_order, action="CANCEL_ORDER_UI", symbol=symbol, orderId=int(cancel_id))
					st.success(f"Canceled orderId={cancel_id}")
				except Exception as e:
					st.error(str(e))

	with logs_tab:
		log_path = os.path.join(os.path.dirname(__file__), "bot.log")
		log_text = tail_log(log_path, max_lines=250)
		st.subheader("Logs (tail)")
		if log_text:
			st.code(log_text)
		else:
			st.write("No logs yet.")
		if auto:
			if os.path.exists(log_path):
				watch_log_and_rerun(log_path, poll_interval=float(interval))
			else:
				time.sleep(int(interval))
				st.rerun()


if __name__ == "__main__":
	main()
