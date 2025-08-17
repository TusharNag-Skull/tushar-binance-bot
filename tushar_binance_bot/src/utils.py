import logging
import re
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any

from binance.exceptions import BinanceAPIException, BinanceOrderException


# Structured logging setup
class ActionFilter(logging.Filter):
	def filter(self, record: logging.LogRecord) -> bool:
		if not hasattr(record, "action"):
			setattr(record, "action", "GENERAL")
		return True


def setup_logger(log_path: str = "bot.log") -> logging.Logger:
	logger = logging.getLogger("bot")
	if logger.handlers:
		return logger
	logger.setLevel(logging.INFO)
	formatter = logging.Formatter(
		fmt='[%(asctime)s] [%(levelname)s] [%(action)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'
	)
	file_handler = logging.FileHandler(log_path)
	file_handler.setFormatter(formatter)
	stream_handler = logging.StreamHandler()
	stream_handler.setFormatter(formatter)
	logger.addHandler(file_handler)
	logger.addHandler(stream_handler)
	logger.addFilter(ActionFilter())
	return logger


logger = setup_logger()


def log_info(message: str, action: str = "GENERAL") -> None:
	logger.info(message, extra={"action": action})


def log_warning(message: str, action: str = "GENERAL") -> None:
	logger.warning(message, extra={"action": action})


def log_error(message: str, action: str = "GENERAL") -> None:
	logger.error(message, extra={"action": action})


@dataclass
class SymbolFilter:
	symbol: str
	tick_size: float
	step_size: float
	min_qty: float
	min_notional: float


def _find_symbol_filters(exchange_info: Dict[str, Any], symbol: str) -> Optional[SymbolFilter]:

	symbol = symbol.upper()
	for s in exchange_info.get("symbols", []):
		if s.get("symbol") == symbol:
			price_filter = next((f for f in s.get("filters", []) if f.get("filterType") == "PRICE_FILTER"), None)
			lot_size = next((f for f in s.get("filters", []) if f.get("filterType") == "LOT_SIZE"), None)
			min_notional = next((f for f in s.get("filters", []) if f.get("filterType") == "MIN_NOTIONAL"), None)
			if not price_filter or not lot_size:
				return None
			return SymbolFilter(
				symbol=symbol,
				tick_size=float(price_filter.get("tickSize", 0.0)),
				step_size=float(lot_size.get("stepSize", 0.0)),
				min_qty=float(lot_size.get("minQty", 0.0)),
				min_notional=float(min_notional.get("notional", 0.0)) if min_notional else 0.0,
			)
	return None


def validate_symbol_format(symbol: str) -> Tuple[bool, str]:
	if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z0-9]{5,20}", symbol.upper()):
		return False, "Symbol must be alphanumeric uppercase like BTCUSDT"
	if not symbol.upper().endswith("USDT"):
		return False, "Only USDT-margined futures symbols are supported (e.g., BTCUSDT)."
	return True, ""


def is_tick_size_compliant(price: float, tick_size: float) -> bool:
	if tick_size == 0:
		return True
	# Check if price aligns with tick size increments
	return round((price / tick_size) - int(price / tick_size), 10) == 0


def is_step_size_compliant(quantity: float, step_size: float) -> bool:
	if step_size == 0:
		return True
	return round((quantity / step_size) - int(quantity / step_size), 10) == 0


def validate_order_inputs(exchange_info: Dict[str, Any], symbol: str, quantity: float, price: Optional[float] = None) -> Tuple[bool, str, Optional[SymbolFilter]]:

	ok, msg = validate_symbol_format(symbol)
	if not ok:
		return False, msg, None
	if quantity is None or quantity <= 0:
		return False, "Quantity must be a positive number.", None

	filters = _find_symbol_filters(exchange_info, symbol)
	if not filters:
		return False, f"Symbol {symbol.upper()} not found or filters missing.", None

	if quantity < filters.min_qty:
		return False, f"Quantity {quantity} is below minQty {filters.min_qty}.", None
	if not is_step_size_compliant(quantity, filters.step_size):
		return False, f"Quantity {quantity} not compliant with stepSize {filters.step_size}.", None

	if price is not None:
		if price <= 0:
			return False, "Price must be positive.", None
		if not is_tick_size_compliant(price, filters.tick_size):
			return False, f"Price {price} not compliant with tickSize {filters.tick_size}.", None

	return True, "", filters


def safe_api_call(fn, *args, action: str = "API_CALL", **kwargs):
	try:
		return fn(*args, **kwargs)
	except (BinanceAPIException, BinanceOrderException) as e:
		log_error(f"Binance API error: {e}", action=action)
		raise
	except Exception as e:
		log_error(f"Unexpected error: {e}", action=action)
		raise


