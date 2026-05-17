"""
position_manager.py - Hidden TP/SL Position Manager for Binance Spot.

Reads open positions from Binance, lets you set server-side TP/SL levels.
Monitors prices via WebSocket and exits at market when levels are hit.
Binance never sees your TP/SL - only market sell orders when triggered.
"""

import hashlib
import hmac
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import requests
import websocket

from flask import Flask, request, jsonify, render_template_string

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("position_manager")

# ─── Binance API helpers ───────────────────────────────────────────

class BinanceClient:
    def __init__(self, api_key: str, api_secret: str, rest_url: str = "https://api.binance.com"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.rest_url = rest_url
        self._exchange_info_cache = {}

    def _sign(self, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000)
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode(), query_string.encode(), hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    def _headers(self) -> dict:
        return {"X-MBX-APIKEY": self.api_key}

    def get_account(self) -> Optional[dict]:
        try:
            params = self._sign({})
            resp = requests.get(
                f"{self.rest_url}/api/v3/account",
                params=params, headers=self._headers(), timeout=10
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"get_account failed: {e}")
            return None

    def get_open_positions(self) -> list:
        """Get all spot balances with non-zero free+locked amounts (excluding stablecoins)."""
        account = self.get_account()
        if not account:
            return []
        positions = []
        skip = {"USDT", "BUSD", "USDC", "FDUSD", "TUSD", "EUR", "USD", "BNB"}
        for b in account.get("balances", []):
            free = float(b["free"])
            locked = float(b["locked"])
            total = free + locked
            if total > 0 and b["asset"] not in skip:
                positions.append({
                    "asset": b["asset"],
                    "symbol": b["asset"] + "USDT",
                    "free": free,
                    "locked": locked,
                    "total": total
                })
        return positions

    def get_symbol_info(self, symbol: str) -> Optional[dict]:
        if symbol in self._exchange_info_cache:
            return self._exchange_info_cache[symbol]
        try:
            resp = requests.get(
                f"{self.rest_url}/api/v3/exchangeInfo",
                params={"symbol": symbol}, timeout=10
            )
            resp.raise_for_status()
            for s in resp.json().get("symbols", []):
                if s["symbol"] == symbol:
                    self._exchange_info_cache[symbol] = s
                    return s
        except Exception as e:
            logger.error(f"exchangeInfo failed for {symbol}: {e}")
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
                        return None
                    return adjusted
        return quantity

    def market_sell(self, symbol: str, quantity: float) -> Optional[dict]:
        adjusted_qty = self._adjust_quantity(symbol, quantity)
        if adjusted_qty is None:
            logger.error(f"Cannot adjust quantity for {symbol}")
            return None

        logger.info(f"MARKET SELL: {adjusted_qty} {symbol}")
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
                params=params, headers=self._headers(), timeout=10
            )
            resp.raise_for_status()
            order = resp.json()
            filled_qty = float(order.get("executedQty", 0))
            filled_quote = float(order.get("cummulativeQuoteQty", 0))
            avg_price = filled_quote / filled_qty if filled_qty > 0 else 0
            logger.info(f"SELL FILLED: {symbol} sold {filled_qty} @ {avg_price:.8g} for {filled_quote:.2f} USDT")
            return {
                "order_id": order.get("orderId"),
                "symbol": symbol,
                "filled_qty": filled_qty,
                "filled_quote": filled_quote,
                "avg_price": avg_price,
                "status": order.get("status")
            }
        except Exception as e:
            logger.error(f"SELL FAILED: {symbol} - {e}")
            return None

    def get_avg_buy_price(self, symbol: str) -> Optional[float]:
        """Get average entry price from recent buy trades."""
        try:
            params = self._sign({"symbol": symbol, "limit": 100})
            resp = requests.get(
                f"{self.rest_url}/api/v3/myTrades",
                params=params, headers=self._headers(), timeout=10
            )
            resp.raise_for_status()
            trades = resp.json()
            buy_trades = [t for t in trades if t["isBuyer"]]
            if not buy_trades:
                return None
            total_qty = sum(float(t["qty"]) for t in buy_trades)
            total_cost = sum(float(t["quoteQty"]) for t in buy_trades)
            if total_qty == 0:
                return None
            return total_cost / total_qty
        except Exception as e:
            logger.error(f"myTrades failed for {symbol}: {e}")
            return None


# ─── Position Manager ──────────────────────────────────────────────

class PositionManager:
    def __init__(self, client: BinanceClient, config: dict):
        self.client = client
        self.config = config
        self.positions = {}  # symbol -> position data
        self.tp_sl = {}      # symbol -> {"tp_pct": float, "sl_pct": float, "tp_price": float, "sl_price": float, "enabled": bool}
        self.prices = {}     # symbol -> current price
        self.closed_trades = []
        self.ws_connected = False
        self._ws_thread = None
        self._running = False
        self._lock = threading.Lock()
        self._tp_sl_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tp_sl_settings.json")
        self._closed_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "closed_trades.json")
        self._load_tp_sl()
        self._load_closed()

    def _load_tp_sl(self):
        try:
            with open(self._tp_sl_file, "r") as f:
                self.tp_sl = json.load(f)
            logger.info(f"Loaded TP/SL settings for {len(self.tp_sl)} positions")
        except (FileNotFoundError, json.JSONDecodeError):
            self.tp_sl = {}

    def _save_tp_sl(self):
        try:
            with open(self._tp_sl_file, "w") as f:
                json.dump(self.tp_sl, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save TP/SL: {e}")

    def _load_closed(self):
        try:
            with open(self._closed_file, "r") as f:
                self.closed_trades = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.closed_trades = []

    def _save_closed(self):
        try:
            with open(self._closed_file, "w") as f:
                json.dump(self.closed_trades, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save closed trades: {e}")

    def refresh_positions(self):
        """Fetch current positions from Binance, filter dust < $1."""
        raw = self.client.get_open_positions()

        # Load manual entry prices
        manual_entries = {}
        efile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manual_entries.json")
        try:
            with open(efile, "r") as f:
                manual_entries = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        # Fetch all current prices in one call
        try:
            resp = requests.get(f"{self.client.rest_url}/api/v3/ticker/price", timeout=10)
            price_map = {t["symbol"]: float(t["price"]) for t in resp.json()}
        except Exception:
            price_map = {}

        with self._lock:
            new_positions = {}
            for p in raw:
                symbol = p["symbol"]
                current = price_map.get(symbol, self.prices.get(symbol, 0))
                if current > 0:
                    self.prices[symbol] = current

                value = p["total"] * current
                if value < 1.0:
                    continue

                # Priority: manual entry > existing > API > current price
                entry_price = manual_entries.get(symbol, 0)
                if entry_price == 0:
                    entry_price = self.positions.get(symbol, {}).get("entry_price", 0)
                if entry_price == 0:
                    entry_price = self.client.get_avg_buy_price(symbol)
                    if entry_price is None:
                        entry_price = current

                new_positions[symbol] = {
                    "asset": p["asset"],
                    "symbol": symbol,
                    "quantity": p["total"],
                    "free": p["free"],
                    "entry_price": entry_price,
                    "current_price": current,
                    "last_update": time.time()
                }
            self.positions = new_positions
        logger.info(f"Loaded {len(new_positions)} positions (filtered dust < $1)")
        return new_positions

    def set_tp_sl(self, symbol: str, tp_pct: float = None, sl_pct: float = None,
                  tp_price: float = None, sl_price: float = None,
                  tp_amount: float = None, sl_amount: float = None,
                  enabled: bool = True):
        """Set TP/SL for a position. Can use percentage, absolute price, or USDT amount."""
        pos = self.positions.get(symbol, {})
        entry_price = pos.get("entry_price", 0)
        quantity = pos.get("quantity", 0)
        position_value = entry_price * quantity if entry_price > 0 else 0

        settings = self.tp_sl.get(symbol, {
            "tp_pct": 0, "sl_pct": 0, "tp_price": 0, "sl_price": 0,
            "tp_amount": 0, "sl_amount": 0, "enabled": False
        })

        if tp_amount is not None and tp_amount > 0 and position_value > 0:
            settings["tp_amount"] = tp_amount
            settings["tp_pct"] = (tp_amount / position_value) * 100
            settings["tp_price"] = entry_price * (1 + settings["tp_pct"] / 100)
        elif tp_pct is not None:
            settings["tp_pct"] = tp_pct
            if entry_price > 0:
                settings["tp_price"] = entry_price * (1 + tp_pct / 100)
            if position_value > 0:
                settings["tp_amount"] = position_value * tp_pct / 100
        elif tp_price is not None:
            settings["tp_price"] = tp_price
            if entry_price > 0:
                settings["tp_pct"] = ((tp_price - entry_price) / entry_price) * 100
                if position_value > 0:
                    settings["tp_amount"] = position_value * settings["tp_pct"] / 100

        if sl_amount is not None and sl_amount > 0 and position_value > 0:
            settings["sl_amount"] = sl_amount
            settings["sl_pct"] = (sl_amount / position_value) * 100
            settings["sl_price"] = entry_price * (1 - settings["sl_pct"] / 100)
        elif sl_pct is not None:
            settings["sl_pct"] = sl_pct
            if entry_price > 0:
                settings["sl_price"] = entry_price * (1 - sl_pct / 100)
            if position_value > 0:
                settings["sl_amount"] = position_value * sl_pct / 100
        elif sl_price is not None:
            settings["sl_price"] = sl_price
            if entry_price > 0:
                settings["sl_pct"] = ((entry_price - sl_price) / entry_price) * 100
                if position_value > 0:
                    settings["sl_amount"] = position_value * settings["sl_pct"] / 100

        settings["enabled"] = enabled
        self.tp_sl[symbol] = settings
        self._save_tp_sl()
        logger.info(f"TP/SL set for {symbol}: TP={settings['tp_price']:.8g} ({settings['tp_pct']:.2f}%, {settings.get('tp_amount',0):.2f} USDT), SL={settings['sl_price']:.8g} ({settings['sl_pct']:.2f}%, {settings.get('sl_amount',0):.2f} USDT)")
        return settings

    def set_tp_sl_all(self, tp_pct: float = None, sl_pct: float = None,
                      tp_amount: float = None, sl_amount: float = None):
        """Apply the same TP/SL to all open positions."""
        results = {}
        for symbol in list(self.positions.keys()):
            results[symbol] = self.set_tp_sl(symbol, tp_pct=tp_pct, sl_pct=sl_pct,
                                             tp_amount=tp_amount, sl_amount=sl_amount, enabled=True)
        return results

    def _check_tp_sl(self, symbol: str, price: float):
        """Check if TP or SL has been hit for a position."""
        settings = self.tp_sl.get(symbol)
        if not settings or not settings.get("enabled"):
            return

        position = self.positions.get(symbol)
        if not position or position["quantity"] <= 0:
            return

        tp_price = settings.get("tp_price", 0)
        sl_price = settings.get("sl_price", 0)

        exit_reason = None
        if tp_price > 0 and price >= tp_price:
            exit_reason = "TP"
        elif sl_price > 0 and price <= sl_price:
            exit_reason = "SL"

        if exit_reason:
            logger.info(f"{exit_reason} HIT for {symbol} @ {price:.8g} (TP={tp_price:.8g}, SL={sl_price:.8g})")
            qty = position["free"]
            if qty <= 0:
                logger.warning(f"No free quantity to sell for {symbol}")
                return

            result = self.client.market_sell(symbol, qty)
            entry_price = position.get("entry_price", 0)
            pnl_pct = ((price - entry_price) / entry_price * 100) if entry_price > 0 else 0
            value = qty * price

            closed = {
                "symbol": symbol,
                "asset": position.get("asset", ""),
                "entry_price": entry_price,
                "exit_price": price,
                "quantity": qty,
                "value_usdt": round(value, 2),
                "pnl_pct": round(pnl_pct, 2),
                "pnl_usdt": round(value * pnl_pct / 100, 2) if pnl_pct else 0,
                "exit_reason": exit_reason,
                "exit_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "order": result
            }
            self.closed_trades.append(closed)
            self._save_closed()

            settings["enabled"] = False
            self._save_tp_sl()

            with self._lock:
                if symbol in self.positions:
                    del self.positions[symbol]

            logger.info(f"CLOSED {symbol}: {exit_reason} @ {price:.8g}, PnL={pnl_pct:+.2f}%")

    def _process_ticker(self, item):
        symbol = item.get("s", "")
        price = float(item.get("c", 0))
        if symbol and price > 0:
            self.prices[symbol] = price
            self._check_tp_sl(symbol, price)

    def _on_ws_message(self, ws, message):
        try:
            data = json.loads(message)
            if "data" in data:
                inner = data["data"]
                if isinstance(inner, list):
                    for item in inner:
                        self._process_ticker(item)
                else:
                    self._process_ticker(inner)
            elif isinstance(data, list):
                for item in data:
                    self._process_ticker(item)
            elif "s" in data:
                self._process_ticker(data)
        except Exception as e:
            logger.error(f"WS message error: {e}")

    def _on_ws_error(self, ws, error):
        logger.error(f"WebSocket error: {error}")
        self.ws_connected = False

    def _on_ws_close(self, ws, code, msg):
        logger.info(f"WebSocket closed: {code} {msg}")
        self.ws_connected = False
        if self._running:
            time.sleep(5)
            self._connect_ws()

    def _on_ws_open(self, ws):
        self.ws_connected = True
        logger.info("WebSocket connected - monitoring prices")

    def _connect_ws(self):
        symbols = list(self.positions.keys())
        if not symbols:
            logger.info("No positions to monitor")
            return

        streams = [f"{s.lower()}@miniTicker" for s in symbols]
        url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(streams)}"
        logger.info(f"Connecting WebSocket for {len(symbols)} positions...")

        ws = websocket.WebSocketApp(
            url,
            on_message=lambda ws, msg: self._on_ws_message(ws, msg),
            on_error=lambda ws, err: self._on_ws_error(ws, err),
            on_close=lambda ws, code, msg: self._on_ws_close(ws, code, msg),
            on_open=lambda ws: self._on_ws_open(ws)
        )
        ws.run_forever()

    def start_monitoring(self):
        if self._ws_thread and self._ws_thread.is_alive():
            return
        self._running = True
        self._ws_thread = threading.Thread(target=self._connect_ws, daemon=True)
        self._ws_thread.start()

    def get_dashboard_data(self):
        positions_list = []
        with self._lock:
            for symbol, pos in list(self.positions.items()):
                current = self.prices.get(symbol, pos.get("current_price", 0))
                entry = pos.get("entry_price", 0)
                pnl_pct = ((current - entry) / entry * 100) if entry > 0 and current > 0 else 0
                value = pos["quantity"] * current

                tp_sl = self.tp_sl.get(symbol, {})
                entry_value = entry * pos["quantity"] if entry > 0 else 0
                pnl_usdt = value - entry_value if entry_value > 0 else 0
                positions_list.append({
                    "symbol": symbol,
                    "asset": pos["asset"],
                    "quantity": pos["quantity"],
                    "entry_price": entry,
                    "current_price": current,
                    "value_usdt": round(value, 2),
                    "entry_value_usdt": round(entry_value, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "pnl_usdt": round(pnl_usdt, 2),
                    "tp_pct": tp_sl.get("tp_pct", 0),
                    "sl_pct": tp_sl.get("sl_pct", 0),
                    "tp_price": tp_sl.get("tp_price", 0),
                    "sl_price": tp_sl.get("sl_price", 0),
                    "tp_amount": tp_sl.get("tp_amount", 0),
                    "sl_amount": tp_sl.get("sl_amount", 0),
                    "tp_sl_enabled": tp_sl.get("enabled", False)
                })

        positions_list.sort(key=lambda x: abs(x["pnl_pct"]), reverse=True)
        total_value = sum(p["value_usdt"] for p in positions_list)
        total_pnl = sum(p["pnl_usdt"] for p in positions_list)

        return {
            "positions": positions_list,
            "closed_trades": self.closed_trades[-50:],
            "total_positions": len(positions_list),
            "total_value_usdt": round(total_value, 2),
            "total_pnl_usdt": round(total_pnl, 2),
            "ws_connected": self.ws_connected
        }


# ─── Flask Dashboard ──────────────────────────────────────────────

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hidden TP/SL Position Manager</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0e17; color: #e0e0e0; }

        .header {
            background: linear-gradient(135deg, #1a1f2e 0%, #0d1117 100%);
            padding: 12px 24px;
            border-bottom: 1px solid #2d333b;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .header h1 { font-size: 18px; color: #58a6ff; }
        .header-stats { display: flex; gap: 20px; font-size: 13px; color: #8b949e; }
        .header-stats .value { color: #e0e0e0; font-weight: 600; }

        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        .status-badge.connected { border: 1px solid #238636; color: #3fb950; }
        .status-badge.disconnected { border: 1px solid #da3633; color: #f85149; }
        .status-dot {
            width: 8px; height: 8px; border-radius: 50%;
        }
        .status-dot.on { background: #3fb950; animation: pulse 2s infinite; }
        .status-dot.off { background: #f85149; }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }

        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }

        .global-controls {
            background: #161b22;
            border: 1px solid #2d333b;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 16px;
            flex-wrap: wrap;
        }
        .global-controls label { font-size: 13px; color: #8b949e; }
        .global-controls input {
            background: #0d1117;
            border: 1px solid #2d333b;
            color: #e0e0e0;
            padding: 6px 10px;
            border-radius: 4px;
            width: 80px;
            font-size: 13px;
        }
        .btn {
            padding: 6px 16px;
            border: none;
            border-radius: 4px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: 0.2s;
        }
        .btn-primary { background: #238636; color: #fff; }
        .btn-primary:hover { background: #2ea043; }
        .btn-danger { background: #da3633; color: #fff; }
        .btn-danger:hover { background: #f85149; }
        .btn-secondary { background: #2d333b; color: #e0e0e0; }
        .btn-secondary:hover { background: #3d444b; }
        .btn-small { padding: 4px 10px; font-size: 12px; }

        .section-title {
            font-size: 16px;
            color: #58a6ff;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .badge { background: #2d333b; padding: 2px 8px; border-radius: 10px; font-size: 12px; color: #8b949e; }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        th {
            background: #161b22;
            padding: 10px 12px;
            text-align: left;
            color: #8b949e;
            font-weight: 600;
            border-bottom: 1px solid #2d333b;
            white-space: nowrap;
        }
        td {
            padding: 10px 12px;
            border-bottom: 1px solid #1a1f2e;
            white-space: nowrap;
        }
        tr:hover { background: #161b22; }
        .pnl-positive { color: #3fb950; font-weight: 600; }
        .pnl-negative { color: #f85149; font-weight: 600; }
        .tp-sl-active { color: #3fb950; }
        .tp-sl-inactive { color: #484f58; }

        .tp-sl-inputs {
            display: flex;
            gap: 4px;
            align-items: center;
        }
        .tp-sl-inputs input {
            background: #0d1117;
            border: 1px solid #2d333b;
            color: #e0e0e0;
            padding: 4px 6px;
            border-radius: 3px;
            width: 70px;
            font-size: 12px;
        }

        .summary-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
            margin-bottom: 20px;
        }
        .card {
            background: #161b22;
            border: 1px solid #2d333b;
            border-radius: 8px;
            padding: 16px;
        }
        .card-label { font-size: 12px; color: #8b949e; margin-bottom: 4px; }
        .card-value { font-size: 24px; font-weight: 700; }

        .closed-section { margin-top: 30px; }

        .empty-state {
            text-align: center;
            padding: 40px;
            color: #484f58;
        }
        .alert-box {
            padding: 10px 16px;
            border-radius: 6px;
            margin-bottom: 12px;
            font-size: 13px;
            display: none;
        }
        .alert-success { background: #0d2818; border: 1px solid #238636; color: #3fb950; }
        .alert-error { background: #2d0a0a; border: 1px solid #da3633; color: #f85149; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Hidden TP/SL Manager</h1>
        <div class="header-stats">
            <span>Positions: <span class="value" id="posCount">0</span></span>
            <span>Portfolio: <span class="value" id="totalValue">--</span> USDT</span>
            <span>PnL: <span class="value" id="totalPnl">--</span></span>
        </div>
        <div id="statusBadge" class="status-badge disconnected">
            <div id="statusDot" class="status-dot off"></div>
            <span id="statusText">Connecting...</span>
        </div>
    </div>

    <div class="container">
        <div id="alertBox" class="alert-box"></div>

        <div class="summary-cards">
            <div class="card">
                <div class="card-label">Open Positions</div>
                <div class="card-value" id="cardPositions">0</div>
            </div>
            <div class="card">
                <div class="card-label">Total Value</div>
                <div class="card-value" id="cardValue">--</div>
            </div>
            <div class="card">
                <div class="card-label">Total PnL</div>
                <div class="card-value" id="cardPnl">--</div>
            </div>
            <div class="card">
                <div class="card-label">Protected (TP/SL set)</div>
                <div class="card-value" id="cardProtected">0</div>
            </div>
        </div>

        <div class="global-controls">
            <span style="font-weight:600; color:#e0e0e0;">Apply to ALL:</span>
            <label>TP %: <input type="number" id="globalTp" step="0.1" min="0" value="50" /></label>
            <label>SL %: <input type="number" id="globalSl" step="0.1" min="0" value="20" /></label>
            <span style="color:#484f58;">|</span>
            <label>TP amt USDT: <input type="number" id="globalTpAmt" step="1" min="0" placeholder="e.g. 100" /></label>
            <label>SL amt USDT: <input type="number" id="globalSlAmt" step="1" min="0" placeholder="e.g. 100" /></label>
            <button class="btn btn-primary" onclick="applyAllTpSl()">Apply to All</button>
            <button class="btn btn-danger" onclick="disableAllTpSl()">Disable All TP/SL</button>
            <button class="btn btn-secondary" onclick="refreshPositions()">Refresh Positions</button>
        </div>

        <div class="section-title">
            Open Positions <span class="badge" id="posCountBadge">0</span>
        </div>
        <div id="positionsTable">
            <div class="empty-state">Loading positions...</div>
        </div>

        <div class="closed-section">
            <div class="section-title">
                Closed Trades (TP/SL triggered) <span class="badge" id="closedCount">0</span>
            </div>
            <div id="closedTable">
                <div class="empty-state">No closed trades yet</div>
            </div>
        </div>
    </div>

    <script>
        var prevClosedCount = -1;

        function playAlert(type) {
            try {
                var ctx = new (window.AudioContext || window.webkitAudioContext)();
                if (type === 'tp') {
                    [800, 1000, 1200].forEach(function(freq, i) {
                        var osc = ctx.createOscillator();
                        var gain = ctx.createGain();
                        osc.connect(gain);
                        gain.connect(ctx.destination);
                        osc.frequency.value = freq;
                        osc.type = 'sine';
                        gain.gain.value = 0.3;
                        osc.start(ctx.currentTime + i * 0.15);
                        osc.stop(ctx.currentTime + i * 0.15 + 0.12);
                    });
                } else {
                    var osc = ctx.createOscillator();
                    var gain = ctx.createGain();
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.frequency.value = 400;
                    osc.type = 'sawtooth';
                    gain.gain.value = 0.25;
                    osc.start(ctx.currentTime);
                    osc.stop(ctx.currentTime + 0.6);
                }
            } catch(e) {}
        }

        function fmt(n, d) {
            if (n === null || n === undefined || n === 0) return '--';
            return Number(n).toFixed(d || 2);
        }
        function fmtPrice(n) {
            if (!n || n === 0) return '--';
            if (n >= 100) return n.toFixed(2);
            if (n >= 1) return n.toFixed(4);
            if (n >= 0.01) return n.toFixed(6);
            return n.toFixed(8);
        }

        function showAlert(msg, type) {
            var box = document.getElementById('alertBox');
            box.textContent = msg;
            box.className = 'alert-box alert-' + type;
            box.style.display = 'block';
            setTimeout(function() { box.style.display = 'none'; }, 4000);
        }

        function applyAllTpSl() {
            var tp = parseFloat(document.getElementById('globalTp').value) || 0;
            var sl = parseFloat(document.getElementById('globalSl').value) || 0;
            var tpAmt = parseFloat(document.getElementById('globalTpAmt').value) || 0;
            var slAmt = parseFloat(document.getElementById('globalSlAmt').value) || 0;
            if (tp <= 0 && sl <= 0 && tpAmt <= 0 && slAmt <= 0) { showAlert('Enter at least TP or SL', 'error'); return; }
            var body = {};
            if (tpAmt > 0) body.tp_amount = tpAmt;
            else if (tp > 0) body.tp_pct = tp;
            if (slAmt > 0) body.sl_amount = slAmt;
            else if (sl > 0) body.sl_pct = sl;
            fetch('/api/tp-sl/all', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            }).then(r => r.json()).then(d => {
                if (d.error) { showAlert(d.error, 'error'); }
                else { showAlert('TP/SL applied to ' + Object.keys(d.results || {}).length + ' positions', 'success'); refresh(); }
            });
        }

        function disableAllTpSl() {
            fetch('/api/tp-sl/disable-all', {method: 'POST'})
            .then(r => r.json()).then(d => {
                showAlert('All TP/SL disabled', 'success');
                refresh();
            });
        }

        function refreshPositions() {
            fetch('/api/refresh', {method: 'POST'})
            .then(r => r.json()).then(d => {
                showAlert('Positions refreshed from Binance (' + (d.count || 0) + ' found)', 'success');
                refresh();
            });
        }

        function setEntry(symbol) {
            var eurEl = document.getElementById('eur_' + symbol);
            if (!eurEl || !eurEl.value) { showAlert('Enter your invested amount in EUR', 'error'); return; }
            fetch('/api/entry/' + symbol, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({invested_eur: parseFloat(eurEl.value)})
            }).then(r => r.json()).then(d => {
                if (d.error) { showAlert(d.error, 'error'); }
                else { showAlert('Entry price updated for ' + symbol, 'success'); refresh(); }
            });
        }

        function setTpSl(symbol) {
            var tpEl = document.getElementById('tp_' + symbol);
            var slEl = document.getElementById('sl_' + symbol);
            var tpPrEl = document.getElementById('tpp_' + symbol);
            var slPrEl = document.getElementById('slp_' + symbol);
            var tpAmtEl = document.getElementById('tpa_' + symbol);
            var slAmtEl = document.getElementById('sla_' + symbol);
            var body = {};
            if (tpAmtEl && tpAmtEl.value) body.tp_amount = parseFloat(tpAmtEl.value);
            else if (tpPrEl && tpPrEl.value) body.tp_price = parseFloat(tpPrEl.value);
            else if (tpEl && tpEl.value) body.tp_pct = parseFloat(tpEl.value);
            if (slAmtEl && slAmtEl.value) body.sl_amount = parseFloat(slAmtEl.value);
            else if (slPrEl && slPrEl.value) body.sl_price = parseFloat(slPrEl.value);
            else if (slEl && slEl.value) body.sl_pct = parseFloat(slEl.value);

            fetch('/api/tp-sl/' + symbol, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            }).then(r => r.json()).then(d => {
                if (d.error) { showAlert(d.error, 'error'); }
                else { showAlert('TP/SL set for ' + symbol, 'success'); refresh(); }
            });
        }

        function disableTpSl(symbol) {
            fetch('/api/tp-sl/' + symbol + '/disable', {method: 'POST'})
            .then(r => r.json()).then(d => {
                showAlert('TP/SL disabled for ' + symbol, 'success');
                refresh();
            });
        }

        function refresh() {
            fetch('/api/data').then(r => r.json()).then(function(data) {
                // Status
                var badge = document.getElementById('statusBadge');
                var dot = document.getElementById('statusDot');
                var text = document.getElementById('statusText');
                if (data.ws_connected) {
                    badge.className = 'status-badge connected';
                    dot.className = 'status-dot on';
                    text.textContent = 'Monitoring';
                } else {
                    badge.className = 'status-badge disconnected';
                    dot.className = 'status-dot off';
                    text.textContent = 'Disconnected';
                }

                // Summary
                document.getElementById('posCount').textContent = data.total_positions;
                document.getElementById('totalValue').textContent = fmt(data.total_value_usdt);
                var pnlEl = document.getElementById('totalPnl');
                pnlEl.textContent = (data.total_pnl_usdt >= 0 ? '+' : '') + fmt(data.total_pnl_usdt) + ' USDT';
                pnlEl.className = 'value ' + (data.total_pnl_usdt >= 0 ? 'pnl-positive' : 'pnl-negative');

                document.getElementById('cardPositions').textContent = data.total_positions;
                document.getElementById('cardValue').textContent = fmt(data.total_value_usdt) + ' USDT';
                var cardPnl = document.getElementById('cardPnl');
                cardPnl.textContent = (data.total_pnl_usdt >= 0 ? '+' : '') + fmt(data.total_pnl_usdt) + ' USDT';
                cardPnl.className = 'card-value ' + (data.total_pnl_usdt >= 0 ? 'pnl-positive' : 'pnl-negative');
                document.getElementById('posCountBadge').textContent = data.total_positions;

                var protectedCount = data.positions.filter(function(p) { return p.tp_sl_enabled; }).length;
                document.getElementById('cardProtected').textContent = protectedCount + '/' + data.total_positions;

                // Positions table
                var div = document.getElementById('positionsTable');
                if (data.positions.length > 0) {
                    var ist = 'style="width:60px;background:#0d1117;border:1px solid #2d333b;color:#e0e0e0;padding:3px 5px;border-radius:3px;font-size:12px;"';
                    var ist2 = 'style="width:80px;background:#0d1117;border:1px solid #2d333b;color:#e0e0e0;padding:3px 5px;border-radius:3px;font-size:12px;"';
                    var html = '<table><tr><th>Coin</th><th>Qty</th><th>Invested EUR</th><th>Entry Price</th><th>Current</th><th>Value USDT</th><th>PnL</th><th>TP %</th><th>SL %</th><th>TP Amt</th><th>SL Amt</th><th>TP Price</th><th>SL Price</th><th>Status</th><th></th></tr>';
                    data.positions.forEach(function(p) {
                        var pnlClass = p.pnl_pct >= 0 ? 'pnl-positive' : 'pnl-negative';
                        var statusClass = p.tp_sl_enabled ? 'tp-sl-active' : 'tp-sl-inactive';
                        var statusText = p.tp_sl_enabled ? 'ACTIVE' : 'OFF';
                        html += '<tr>';
                        var investedEur = p.entry_value_usdt > 0 ? (p.entry_value_usdt / 1.13).toFixed(0) : '';
                        html += '<td><strong>' + p.asset + '</strong></td>';
                        html += '<td>' + fmt(p.quantity, 4) + '</td>';
                        html += '<td><input type="number" id="eur_' + p.symbol + '" value="' + investedEur + '" step="1" min="0" placeholder="EUR" ' + ist2 + '/> <button class="btn btn-secondary btn-small" onclick="setEntry(\'' + p.symbol + '\')" style="padding:2px 6px;font-size:11px;">Fix</button></td>';
                        html += '<td>' + fmtPrice(p.entry_price) + '</td>';
                        html += '<td>' + fmtPrice(p.current_price) + '</td>';
                        html += '<td>' + fmt(p.value_usdt) + '</td>';
                        html += '<td class="' + pnlClass + '">' + (p.pnl_pct >= 0 ? '+' : '') + fmt(p.pnl_pct) + '% (' + (p.pnl_usdt >= 0 ? '+' : '') + fmt(p.pnl_usdt) + ')</td>';
                        html += '<td><input type="number" id="tp_' + p.symbol + '" value="' + (p.tp_pct || '') + '" step="0.1" min="0" ' + ist + '/></td>';
                        html += '<td><input type="number" id="sl_' + p.symbol + '" value="' + (p.sl_pct || '') + '" step="0.1" min="0" ' + ist + '/></td>';
                        html += '<td><input type="number" id="tpa_' + p.symbol + '" value="' + (p.tp_amount || '') + '" step="1" min="0" placeholder="USDT" ' + ist2 + '/></td>';
                        html += '<td><input type="number" id="sla_' + p.symbol + '" value="' + (p.sl_amount || '') + '" step="1" min="0" placeholder="USDT" ' + ist2 + '/></td>';
                        html += '<td><input type="number" id="tpp_' + p.symbol + '" value="' + (p.tp_price ? fmtPrice(p.tp_price) : '') + '" step="any" min="0" ' + ist2 + '/></td>';
                        html += '<td><input type="number" id="slp_' + p.symbol + '" value="' + (p.sl_price ? fmtPrice(p.sl_price) : '') + '" step="any" min="0" ' + ist2 + '/></td>';
                        html += '<td class="' + statusClass + '">' + statusText + '</td>';
                        html += '<td><button class="btn btn-primary btn-small" onclick="setTpSl(\'' + p.symbol + '\')">Set</button> ';
                        if (p.tp_sl_enabled) {
                            html += '<button class="btn btn-danger btn-small" onclick="disableTpSl(\'' + p.symbol + '\')">Off</button>';
                        }
                        html += '</td>';
                        html += '</tr>';
                    });
                    html += '</table>';
                    div.innerHTML = html;
                } else {
                    div.innerHTML = '<div class="empty-state">No open positions found. Click "Refresh Positions" to fetch from Binance.</div>';
                }

                // Closed trades
                document.getElementById('closedCount').textContent = data.closed_trades.length;
                var closedDiv = document.getElementById('closedTable');
                if (data.closed_trades.length > 0) {
                    if (prevClosedCount >= 0 && data.closed_trades.length > prevClosedCount) {
                        var lastClosed = data.closed_trades[data.closed_trades.length - 1];
                        playAlert(lastClosed.exit_reason === 'TP' ? 'tp' : 'sl');
                    }

                    var ch = '<table><tr><th>Time</th><th>Coin</th><th>Entry</th><th>Exit</th><th>Value</th><th>PnL</th><th>Reason</th></tr>';
                    data.closed_trades.slice().reverse().forEach(function(t) {
                        var pnlClass = t.pnl_pct >= 0 ? 'pnl-positive' : 'pnl-negative';
                        ch += '<tr>';
                        ch += '<td>' + t.exit_time + '</td>';
                        ch += '<td><strong>' + (t.asset || t.symbol) + '</strong></td>';
                        ch += '<td>' + fmtPrice(t.entry_price) + '</td>';
                        ch += '<td>' + fmtPrice(t.exit_price) + '</td>';
                        ch += '<td>' + fmt(t.value_usdt) + ' USDT</td>';
                        ch += '<td class="' + pnlClass + '">' + (t.pnl_pct >= 0 ? '+' : '') + fmt(t.pnl_pct) + '%</td>';
                        ch += '<td>' + t.exit_reason + '</td>';
                        ch += '</tr>';
                    });
                    ch += '</table>';
                    closedDiv.innerHTML = ch;
                } else {
                    closedDiv.innerHTML = '<div class="empty-state">No closed trades yet</div>';
                }
                prevClosedCount = data.closed_trades.length;
            }).catch(function(e) {
                document.getElementById('statusText').textContent = 'Error';
            });
        }

        setInterval(refresh, 3000);
        refresh();
    </script>
</body>
</html>
"""


def create_app(config: dict):
    app = Flask(__name__)

    client = BinanceClient(
        api_key=config.get("trading", {}).get("binance_api_key", ""),
        api_secret=config.get("trading", {}).get("binance_api_secret", ""),
        rest_url=config.get("binance", {}).get("rest_url", "https://api.binance.com")
    )

    manager = PositionManager(client, config)
    manager.refresh_positions()
    manager.start_monitoring()

    @app.route("/")
    def index():
        return render_template_string(DASHBOARD_HTML)

    @app.route("/api/data")
    def api_data():
        return jsonify(manager.get_dashboard_data())

    @app.route("/api/refresh", methods=["POST"])
    def api_refresh():
        positions = manager.refresh_positions()
        manager.start_monitoring()
        return jsonify({"status": "ok", "count": len(positions)})

    @app.route("/api/entry/<symbol>", methods=["POST"])
    def api_set_entry(symbol):
        data = request.get_json() or {}
        entry_price = data.get("entry_price")
        invested_eur = data.get("invested_eur")
        with manager._lock:
            if symbol in manager.positions:
                if invested_eur and invested_eur > 0:
                    qty = manager.positions[symbol]["quantity"]
                    try:
                        r = requests.get(f"{client.rest_url}/api/v3/ticker/price", params={"symbol": "EURUSDT"}, timeout=5)
                        eur_rate = float(r.json()["price"])
                    except Exception:
                        eur_rate = 1.13
                    invested_usdt = invested_eur * eur_rate
                    entry_price = invested_usdt / qty if qty > 0 else 0
                if entry_price and entry_price > 0:
                    manager.positions[symbol]["entry_price"] = entry_price
                    entries = {}
                    efile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manual_entries.json")
                    try:
                        with open(efile, "r") as f:
                            entries = json.load(f)
                    except (FileNotFoundError, json.JSONDecodeError):
                        pass
                    entries[symbol] = entry_price
                    with open(efile, "w") as f:
                        json.dump(entries, f, indent=2)
                    return jsonify({"status": "ok", "entry_price": entry_price})
        return jsonify({"error": "Position not found"}), 404

    @app.route("/api/tp-sl/<symbol>", methods=["POST"])
    def api_set_tp_sl(symbol):
        data = request.get_json() or {}
        try:
            result = manager.set_tp_sl(
                symbol,
                tp_pct=data.get("tp_pct"),
                sl_pct=data.get("sl_pct"),
                tp_price=data.get("tp_price"),
                sl_price=data.get("sl_price"),
                tp_amount=data.get("tp_amount"),
                sl_amount=data.get("sl_amount"),
                enabled=True
            )
            return jsonify({"status": "ok", "settings": result})
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/api/tp-sl/<symbol>/disable", methods=["POST"])
    def api_disable_tp_sl(symbol):
        if symbol in manager.tp_sl:
            manager.tp_sl[symbol]["enabled"] = False
            manager._save_tp_sl()
        return jsonify({"status": "ok"})

    @app.route("/api/tp-sl/all", methods=["POST"])
    def api_set_all_tp_sl():
        data = request.get_json() or {}
        results = manager.set_tp_sl_all(
            tp_pct=data.get("tp_pct"), sl_pct=data.get("sl_pct"),
            tp_amount=data.get("tp_amount"), sl_amount=data.get("sl_amount")
        )
        return jsonify({"status": "ok", "results": {k: v for k, v in results.items()}})

    @app.route("/api/tp-sl/disable-all", methods=["POST"])
    def api_disable_all_tp_sl():
        for symbol in manager.tp_sl:
            manager.tp_sl[symbol]["enabled"] = False
        manager._save_tp_sl()
        return jsonify({"status": "ok"})

    return app


def main():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(config_path) as f:
        config = json.load(f)

    port = config.get("dashboard", {}).get("port", 5060)
    app = create_app(config)

    logger.info(f"Starting Hidden TP/SL Manager on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
