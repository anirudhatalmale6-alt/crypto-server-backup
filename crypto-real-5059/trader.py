"""
trader.py - Binance real trading module.

Places real market orders on Binance when in LIVE mode.
TP/SL levels are managed internally - Binance only sees market orders.
"""

import hashlib
import hmac
import time
import logging
from typing import Optional
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)


class BinanceTrader:
    """Handles real order execution on Binance."""

    def __init__(self, config: dict):
        trading_cfg = config.get("trading", {})
        self.api_key = trading_cfg.get("binance_api_key", "")
        self.api_secret = trading_cfg.get("binance_api_secret", "")
        self.live_mode = trading_cfg.get("mode", "demo") == "live"
        self.rest_url = config.get("binance", {}).get("rest_url", "https://api.binance.com")

        if self.live_mode and (not self.api_key or self.api_key == "YOUR_API_KEY"):
            logger.error("LIVE mode enabled but no valid Binance API key configured!")
            logger.error("Falling back to DEMO mode for safety.")
            self.live_mode = False

        mode_str = "LIVE" if self.live_mode else "DEMO"
        logger.info(f"Trading mode: {mode_str}")

        self._exchange_info_cache = {}

    def _sign(self, params: dict) -> dict:
        """Add timestamp and HMAC-SHA256 signature to request parameters."""
        params["timestamp"] = int(time.time() * 1000)
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    def _headers(self) -> dict:
        return {"X-MBX-APIKEY": self.api_key}

    def get_symbol_info(self, symbol: str) -> Optional[dict]:
        """Get trading rules for a symbol (lot size, min notional, etc.)."""
        if symbol in self._exchange_info_cache:
            return self._exchange_info_cache[symbol]

        try:
            url = f"{self.rest_url}/api/v3/exchangeInfo"
            resp = requests.get(url, params={"symbol": symbol}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            for s in data.get("symbols", []):
                if s["symbol"] == symbol:
                    self._exchange_info_cache[symbol] = s
                    return s
        except Exception as e:
            logger.error(f"Failed to get exchange info for {symbol}: {e}")
        return None

    def _adjust_quantity(self, symbol: str, quantity: float) -> Optional[float]:
        """Adjust quantity to match Binance LOT_SIZE filter."""
        info = self.get_symbol_info(symbol)
        if not info:
            return None

        for f in info.get("filters", []):
            if f["filterType"] == "LOT_SIZE":
                step_size = float(f["stepSize"])
                min_qty = float(f["minQty"])
                if step_size > 0:
                    precision = len(f["stepSize"].rstrip("0").split(".")[-1]) if "." in f["stepSize"] else 0
                    adjusted = round(quantity - (quantity % step_size), precision)
                    if adjusted < min_qty:
                        logger.warning(f"{symbol}: quantity {adjusted} below minimum {min_qty}")
                        return None
                    return adjusted
        return quantity

    def get_account_balance(self, asset: str = "USDT") -> Optional[float]:
        """Get available balance for an asset."""
        if not self.live_mode:
            return None

        try:
            params = self._sign({})
            resp = requests.get(
                f"{self.rest_url}/api/v3/account",
                params=params,
                headers=self._headers(),
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            for b in data.get("balances", []):
                if b["asset"] == asset:
                    return float(b["free"])
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
        return None

    def market_buy(self, symbol: str, quote_amount: float) -> Optional[dict]:
        """
        Place a market buy order using quoteOrderQty (spend exact USDT amount).
        Returns order result dict or None on failure.
        """
        if not self.live_mode:
            logger.info(f"DEMO: Would buy {symbol} for {quote_amount} USDT")
            return None

        logger.info(f"LIVE ORDER: Market BUY {symbol} for {quote_amount} USDT")

        try:
            params = {
                "symbol": symbol,
                "side": "BUY",
                "type": "MARKET",
                "quoteOrderQty": f"{quote_amount:.2f}"
            }
            params = self._sign(params)

            resp = requests.post(
                f"{self.rest_url}/api/v3/order",
                params=params,
                headers=self._headers(),
                timeout=10
            )
            resp.raise_for_status()
            order = resp.json()

            filled_qty = float(order.get("executedQty", 0))
            filled_quote = float(order.get("cummulativeQuoteQty", 0))
            avg_price = filled_quote / filled_qty if filled_qty > 0 else 0

            logger.info(
                f"LIVE ORDER FILLED: {symbol} bought {filled_qty} "
                f"@ avg {avg_price:.8g} for {filled_quote:.2f} USDT "
                f"[Order #{order.get('orderId')}]"
            )
            return {
                "order_id": order.get("orderId"),
                "symbol": symbol,
                "side": "BUY",
                "filled_qty": filled_qty,
                "filled_quote": filled_quote,
                "avg_price": avg_price,
                "status": order.get("status")
            }

        except requests.exceptions.HTTPError as e:
            error_data = {}
            try:
                error_data = e.response.json()
            except Exception:
                pass
            logger.error(
                f"LIVE ORDER FAILED: {symbol} - {e} - {error_data}"
            )
            return None
        except Exception as e:
            logger.error(f"LIVE ORDER ERROR: {symbol} - {e}")
            return None

    def market_sell(self, symbol: str, quantity: float) -> Optional[dict]:
        """
        Place a market sell order for a specific quantity.
        Returns order result dict or None on failure.
        """
        if not self.live_mode:
            logger.info(f"DEMO: Would sell {quantity} {symbol}")
            return None

        adjusted_qty = self._adjust_quantity(symbol, quantity)
        if adjusted_qty is None:
            logger.error(f"Cannot adjust quantity for {symbol}")
            return None

        logger.info(f"LIVE ORDER: Market SELL {adjusted_qty} {symbol}")

        try:
            params = {
                "symbol": symbol,
                "side": "SELL",
                "type": "MARKET",
                "quantity": f"{adjusted_qty}"
            }
            params = self._sign(params)

            resp = requests.post(
                f"{self.rest_url}/api/v3/order",
                params=params,
                headers=self._headers(),
                timeout=10
            )
            resp.raise_for_status()
            order = resp.json()

            filled_qty = float(order.get("executedQty", 0))
            filled_quote = float(order.get("cummulativeQuoteQty", 0))
            avg_price = filled_quote / filled_qty if filled_qty > 0 else 0

            logger.info(
                f"LIVE ORDER FILLED: {symbol} sold {filled_qty} "
                f"@ avg {avg_price:.8g} for {filled_quote:.2f} USDT "
                f"[Order #{order.get('orderId')}]"
            )
            return {
                "order_id": order.get("orderId"),
                "symbol": symbol,
                "side": "SELL",
                "filled_qty": filled_qty,
                "filled_quote": filled_quote,
                "avg_price": avg_price,
                "status": order.get("status")
            }

        except requests.exceptions.HTTPError as e:
            error_data = {}
            try:
                error_data = e.response.json()
            except Exception:
                pass
            logger.error(
                f"LIVE SELL FAILED: {symbol} - {e} - {error_data}"
            )
            return None
        except Exception as e:
            logger.error(f"LIVE SELL ERROR: {symbol} - {e}")
            return None
