"""
trader.py - Binance real trading module (USDC spot only).

Monitors USDT pairs for detection, trades via USDC pairs on Binance.
TP/SL levels are managed internally - Binance only sees market orders.
"""

import hashlib
import hmac
import time
import json
import os
import logging
from typing import Optional
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

_FAILED_SELLS_FILE = "/opt/crypto-shared/failed_sells.json"

def _save_failed_sell(port, symbol, quantity, reason):
    try:
        os.makedirs(os.path.dirname(_FAILED_SELLS_FILE), exist_ok=True)
        data = []
        if os.path.exists(_FAILED_SELLS_FILE):
            with open(_FAILED_SELLS_FILE, "r") as f:
                data = json.load(f)
        data.append({
            "port": port,
            "symbol": symbol,
            "quantity": quantity,
            "reason": reason,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "ts": time.time()
        })
        data = [d for d in data if time.time() - d.get("ts", 0) < 86400]
        with open(_FAILED_SELLS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save failed sell record: {e}")


class BinanceTrader:
    """Handles real order execution on Binance via USDC spot pairs."""

    def __init__(self, config: dict, port=0):
        trading_cfg = config.get("trading", {})
        self.api_key = trading_cfg.get("binance_api_key", "")
        self.api_secret = trading_cfg.get("binance_api_secret", "")
        self.live_mode = trading_cfg.get("mode", "demo") == "live"
        self.rest_url = config.get("binance", {}).get("rest_url", "https://api.binance.com")
        self.port = port or config.get("dashboard", {}).get("port", 0)

        if self.live_mode and (not self.api_key or self.api_key == "YOUR_API_KEY"):
            logger.error("LIVE mode enabled but no valid Binance API key configured!")
            logger.error("Falling back to DEMO mode for safety.")
            self.live_mode = False

        mode_str = "LIVE" if self.live_mode else "DEMO"
        logger.info(f"Trading mode: {mode_str} (USDC spot only)")

        self._exchange_info_cache = {}
        self._usdc_pairs_cache = None

    def _to_usdc_symbol(self, symbol: str) -> str:
        if symbol.endswith("USDT"):
            return symbol[:-4] + "USDC"
        return symbol

    def _usdc_pair_exists(self, usdc_symbol: str) -> bool:
        if self._usdc_pairs_cache is None:
            try:
                resp = requests.get(f"{self.rest_url}/api/v3/exchangeInfo", timeout=15)
                resp.raise_for_status()
                self._usdc_pairs_cache = set(
                    s["symbol"] for s in resp.json().get("symbols", [])
                    if s["symbol"].endswith("USDC") and s["status"] == "TRADING"
                )
                logger.info(f"Loaded {len(self._usdc_pairs_cache)} USDC trading pairs")
            except Exception as e:
                logger.error(f"Failed to load USDC pairs: {e}")
                self._usdc_pairs_cache = set()
        return usdc_symbol in self._usdc_pairs_cache

    def _sign(self, params: dict) -> dict:
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

    def get_account_balance(self, asset: str = "USDC") -> Optional[float]:
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


    # --- Convert API (USDC->EUR->coin fallback) ---

    MAX_CONVERT_EUR = 195.0
    MIN_CONVERT_EUR = 5.0

    def _single_convert(self, from_asset: str, to_asset: str, quantity: float):
        if from_asset == "EUR":
            amount_str = f"{quantity:.2f}"
        else:
            amount_str = f"{quantity:.8g}"
        params = self._sign({
            "fromAsset": from_asset,
            "toAsset": to_asset,
            "fromAmount": amount_str,
            "validTime": "10s"
        })
        try:
            resp = requests.post(
                f"{self.rest_url}/sapi/v1/convert/getQuote",
                params=params, headers=self._headers(), timeout=10
            )
            if resp.status_code != 200:
                err = resp.text[:200]
                logger.error(f"Convert getQuote failed {from_asset}->{to_asset}: {resp.status_code} {err}")
                return None
            quote = resp.json()
            quote_id = quote.get("quoteId")
            if not quote_id:
                logger.error(f"Convert no quoteId: {quote}")
                return None
            accept = requests.post(
                f"{self.rest_url}/sapi/v1/convert/acceptQuote",
                params=self._sign({"quoteId": quote_id}),
                headers=self._headers(), timeout=10
            )
            if accept.status_code != 200:
                logger.error(f"Convert acceptQuote failed: {accept.status_code} {accept.text[:200]}")
                return None
            result = accept.json()
            if result.get("orderStatus") != "SUCCESS":
                logger.error(f"Convert order not SUCCESS: {result}")
                return None
            logger.info(f"CONVERT OK: {from_asset}->{to_asset} qty={amount_str} "
                        f"fromAmt={result.get('fromAmount')} toAmt={result.get('toAmount')}")
            return {
                "from_amount": float(result.get("fromAmount", 0)),
                "to_amount": float(result.get("toAmount", 0)),
                "from_asset": from_asset,
                "to_asset": to_asset,
                "status": "FILLED",
                "method": "CONVERT"
            }
        except Exception as e:
            logger.error(f"Convert error {from_asset}->{to_asset}: {e}")
            return None

    def _convert_chunked(self, from_asset: str, to_asset: str, total_eur: float):
        remaining = total_eur
        total_to = 0.0
        total_from = 0.0
        while remaining >= self.MIN_CONVERT_EUR:
            chunk = min(remaining, self.MAX_CONVERT_EUR)
            result = self._single_convert(from_asset, to_asset, chunk)
            if result is None:
                break
            total_from += result["from_amount"]
            total_to += result["to_amount"]
            remaining -= chunk
            if remaining >= self.MIN_CONVERT_EUR:
                time.sleep(0.5)
        if total_to <= 0:
            return None
        return {
            "from_amount": total_from,
            "to_amount": total_to,
            "from_asset": from_asset,
            "to_asset": to_asset,
            "status": "FILLED",
            "method": "CONVERT"
        }

    def _convert_buy_via_eur(self, symbol: str, usdc_amount: float):
        """Buy a coin that has no USDC pair: USDC->EUR->coin via Convert."""
        asset = symbol.replace("USDT", "").replace("USDC", "")
        logger.info(f"CONVERT BUY FALLBACK: {asset} - converting {usdc_amount:.2f} USDC to EUR first")

        # Step 1: Convert USDC to EUR
        usdc_to_eur = self._single_convert("USDC", "EUR", usdc_amount)
        if usdc_to_eur is None:
            logger.error(f"CONVERT BUY FAILED: could not convert USDC to EUR")
            return None
        eur_amount = usdc_to_eur["to_amount"]
        logger.info(f"CONVERT BUY: got {eur_amount:.2f} EUR from {usdc_amount:.2f} USDC")

        # Step 2: Convert EUR to coin
        if eur_amount > self.MAX_CONVERT_EUR:
            buy_result = self._convert_chunked("EUR", asset, eur_amount)
        else:
            buy_result = self._single_convert("EUR", asset, eur_amount)

        if buy_result is None:
            logger.error(f"CONVERT BUY FAILED: could not buy {asset} with {eur_amount:.2f} EUR, "
                        f"EUR is now in your account (not USDC)")
            return None

        filled_qty = buy_result["to_amount"]
        logger.info(f"CONVERT BUY FILLED: bought {filled_qty:.8g} {asset} via Convert "
                    f"({usdc_amount:.2f} USDC -> {eur_amount:.2f} EUR -> {filled_qty:.8g} {asset})")

        # Get current price for avg_price estimate
        avg_price = usdc_amount / filled_qty if filled_qty > 0 else 0

        return {
            "order_id": f"convert_{int(time.time())}",
            "symbol": asset + "USDC",
            "side": "BUY",
            "filled_qty": filled_qty,
            "filled_quote": usdc_amount,
            "avg_price": avg_price,
            "status": "FILLED",
            "method": "CONVERT_VIA_EUR"
        }

    def _convert_sell_via_eur(self, symbol: str, quantity: float):
        """Sell a coin that has no USDC pair: coin->EUR->USDC via Convert."""
        asset = symbol.replace("USDT", "").replace("USDC", "")
        logger.info(f"CONVERT SELL FALLBACK: selling {quantity:.8g} {asset} via EUR")

        # Step 1: Convert coin to EUR
        sell_result = self._single_convert(asset, "EUR", quantity)
        if sell_result is None:
            logger.error(f"CONVERT SELL FAILED: could not convert {asset} to EUR")
            return None
        eur_amount = sell_result["to_amount"]
        logger.info(f"CONVERT SELL: got {eur_amount:.2f} EUR from {quantity:.8g} {asset}")

        # Step 2: Convert EUR back to USDC
        if eur_amount >= self.MIN_CONVERT_EUR:
            eur_to_usdc = self._convert_chunked("EUR", "USDC", eur_amount) if eur_amount > self.MAX_CONVERT_EUR else self._single_convert("EUR", "USDC", eur_amount)
            if eur_to_usdc:
                usdc_received = eur_to_usdc["to_amount"]
                logger.info(f"CONVERT SELL: converted {eur_amount:.2f} EUR back to {usdc_received:.2f} USDC")
            else:
                usdc_received = 0
                logger.warning(f"CONVERT SELL: EUR->USDC failed, {eur_amount:.2f} EUR left in account")
        else:
            usdc_received = 0
            logger.warning(f"CONVERT SELL: EUR amount {eur_amount:.2f} too small to convert back to USDC")

        avg_price = usdc_received / quantity if quantity > 0 else 0
        return {
            "order_id": f"convert_{int(time.time())}",
            "symbol": asset + "USDC",
            "side": "SELL",
            "filled_qty": quantity,
            "filled_quote": usdc_received,
            "avg_price": avg_price,
            "status": "FILLED",
            "method": "CONVERT_VIA_EUR"
        }

    def market_buy(self, symbol: str, quote_amount: float) -> Optional[dict]:
        usdc_symbol = self._to_usdc_symbol(symbol)

        if not self.live_mode:
            logger.info(f"DEMO: Would buy {usdc_symbol} for {quote_amount} USDC")
            return None

        if not self._usdc_pair_exists(usdc_symbol):
            logger.info(f"USDC pair {usdc_symbol} not available, trying Convert fallback (USDC->EUR->coin)")
            return self._convert_buy_via_eur(symbol, quote_amount)

        logger.info(f"LIVE BUY: {usdc_symbol} for {quote_amount} USDC (detected on {symbol})")

        try:
            params = {
                "symbol": usdc_symbol,
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
                f"LIVE BUY FILLED: {usdc_symbol} bought {filled_qty} "
                f"@ avg {avg_price:.8g} for {filled_quote:.2f} USDC "
                f"[Order #{order.get('orderId')}]"
            )
            return {
                "order_id": order.get("orderId"),
                "symbol": usdc_symbol,
                "side": "BUY",
                "filled_qty": filled_qty,
                "filled_quote": filled_quote,
                "avg_price": avg_price,
                "status": order.get("status"),
                "method": "SPOT_USDC"
            }

        except requests.exceptions.HTTPError as e:
            error_data = {}
            try:
                error_data = e.response.json()
            except Exception:
                pass
            status_code = e.response.status_code if e.response is not None else 0
            if status_code in (418, 429):
                logger.warning(f"LIVE BUY rate limited ({status_code}): {usdc_symbol} - retrying up to 10 times...")
                for attempt in range(1, 11):
                    time.sleep(10)
                    logger.info(f"LIVE BUY retry {attempt}/10: {usdc_symbol}")
                    try:
                        params = {
                            "symbol": usdc_symbol,
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
                        logger.info(f"LIVE BUY FILLED (retry {attempt}): {usdc_symbol} bought {filled_qty} @ avg {avg_price:.8g} for {filled_quote:.2f} USDC")
                        return {
                            "order_id": order.get("orderId"),
                            "symbol": usdc_symbol,
                            "side": "BUY",
                            "filled_qty": filled_qty,
                            "filled_quote": filled_quote,
                            "avg_price": avg_price,
                            "status": order.get("status"),
                            "method": "SPOT_USDC"
                        }
                    except requests.exceptions.HTTPError as re:
                        rc = re.response.status_code if re.response is not None else 0
                        if rc not in (418, 429):
                            logger.error(f"LIVE BUY retry {attempt} failed (non-rate-limit): {re}")
                            return None
                        logger.warning(f"LIVE BUY retry {attempt} still rate limited ({rc})")
                    except Exception as re:
                        logger.error(f"LIVE BUY retry {attempt} error: {re}")
                        return None
                logger.error(f"LIVE BUY FAILED after 10 retries: {usdc_symbol}")
                _save_failed_sell(self.port, usdc_symbol, quote_amount, "BUY rate limited after 10 retries")
                return None
            logger.error(f"LIVE BUY FAILED: {usdc_symbol} - {e} - {error_data}")
            return None
        except Exception as e:
            logger.error(f"LIVE BUY ERROR: {usdc_symbol} - {e}")
            return None

    def market_sell(self, symbol: str, quantity: float) -> Optional[dict]:
        usdc_symbol = self._to_usdc_symbol(symbol)

        if not self.live_mode:
            logger.info(f"DEMO: Would sell {quantity} {usdc_symbol}")
            return None

        if not self._usdc_pair_exists(usdc_symbol):
            logger.info(f"USDC pair {usdc_symbol} not available, trying Convert fallback (coin->EUR->USDC)")
            return self._convert_sell_via_eur(symbol, quantity)

        adjusted_qty = self._adjust_quantity(usdc_symbol, quantity)
        if adjusted_qty is None:
            logger.error(f"Cannot adjust quantity for {usdc_symbol}")
            return None

        logger.info(f"LIVE SELL: {adjusted_qty} {usdc_symbol}")

        try:
            params = {
                "symbol": usdc_symbol,
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
                f"LIVE SELL FILLED: {usdc_symbol} sold {filled_qty} "
                f"@ avg {avg_price:.8g} for {filled_quote:.2f} USDC "
                f"[Order #{order.get('orderId')}]"
            )
            return {
                "order_id": order.get("orderId"),
                "symbol": usdc_symbol,
                "side": "SELL",
                "filled_qty": filled_qty,
                "filled_quote": filled_quote,
                "avg_price": avg_price,
                "status": order.get("status"),
                "method": "SPOT_USDC"
            }

        except requests.exceptions.HTTPError as e:
            error_data = {}
            try:
                error_data = e.response.json()
            except Exception:
                pass
            status_code = e.response.status_code if e.response is not None else 0
            if status_code in (418, 429):
                logger.warning(f"LIVE SELL rate limited ({status_code}): {usdc_symbol} - retrying up to 10 times...")
                for attempt in range(1, 11):
                    time.sleep(10)
                    logger.info(f"LIVE SELL retry {attempt}/10: {usdc_symbol}")
                    try:
                        params = {
                            "symbol": usdc_symbol,
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
                        logger.info(f"LIVE SELL FILLED (retry {attempt}): {usdc_symbol} sold {filled_qty} @ avg {avg_price:.8g} for {filled_quote:.2f} USDC")
                        return {
                            "order_id": order.get("orderId"),
                            "symbol": usdc_symbol,
                            "side": "SELL",
                            "filled_qty": filled_qty,
                            "filled_quote": filled_quote,
                            "avg_price": avg_price,
                            "status": order.get("status"),
                            "method": "SPOT_USDC"
                        }
                    except requests.exceptions.HTTPError as re:
                        rc = re.response.status_code if re.response is not None else 0
                        if rc not in (418, 429):
                            logger.error(f"LIVE SELL retry {attempt} failed (non-rate-limit): {re}")
                            return None
                        logger.warning(f"LIVE SELL retry {attempt} still rate limited ({rc})")
                    except Exception as re:
                        logger.error(f"LIVE SELL retry {attempt} error: {re}")
                        return None
                logger.error(f"LIVE SELL FAILED after 10 retries: {usdc_symbol}")
                _save_failed_sell(self.port, usdc_symbol, adjusted_qty, "SELL rate limited after 10 retries")
                return None
            logger.error(f"LIVE SELL FAILED: {usdc_symbol} - {e} - {error_data}")
            return None
        except Exception as e:
            logger.error(f"LIVE SELL ERROR: {usdc_symbol} - {e}")
            return None
