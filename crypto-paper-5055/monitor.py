"""
monitor.py - Binance WebSocket price monitoring and crash detection logic.

Connects to Binance public WebSocket streams, tracks prices in rolling windows,
and detects significant price drops.
"""

import asyncio
import json
import os
import time
import logging
import threading
from collections import deque
from typing import Dict, List, Optional, Tuple

import requests
import websockets

from database import Database
from alerts import AlertManager
from trader import BinanceTrader

logger = logging.getLogger(__name__)


class PriceWindow:
    """Maintains a rolling window of price data for a single symbol."""

    def __init__(self, max_window_seconds: int = 900):
        """
        Args:
            max_window_seconds: Maximum time window to keep prices (default 15 min).
        """
        self.max_window_seconds = max_window_seconds
        # deque of (timestamp, price) tuples
        self.prices: deque = deque()
        self.current_price: float = 0.0
        self.last_update: float = 0.0

    def add_price(self, price: float, timestamp: float = None):
        """Add a price point."""
        if timestamp is None:
            timestamp = time.time()
        self.prices.append((timestamp, price))
        self.current_price = price
        self.last_update = timestamp
        self._cleanup(timestamp)

    def _cleanup(self, now: float):
        """Remove entries older than max window."""
        cutoff = now - self.max_window_seconds
        while self.prices and self.prices[0][0] < cutoff:
            self.prices.popleft()

    def get_max_price_in_window(self, window_seconds: int) -> Optional[Tuple[float, float]]:
        """
        Get the maximum price within the given time window.
        Returns (max_price, timestamp_of_max) or None if no data.
        """
        if not self.prices:
            return None
        now = time.time()
        cutoff = now - window_seconds
        max_price = 0.0
        max_ts = 0.0
        try:
            _snap = list(self.prices)
        except RuntimeError:
            _snap = []
        for ts, price in _snap:
            if ts >= cutoff and price > max_price:
                max_price = price
                max_ts = ts
        if max_price == 0.0:
            return None
        return (max_price, max_ts)

    def get_min_price_in_window(self, window_seconds: int) -> Optional[Tuple[float, float]]:
        """
        Get the minimum price within the given time window.
        Returns (min_price, timestamp_of_min) or None if no data.
        """
        if not self.prices:
            return None
        now = time.time()
        cutoff = now - window_seconds
        min_price = float('inf')
        min_ts = 0.0
        try:
            _snap = list(self.prices)
        except RuntimeError:
            _snap = []
        for ts, price in _snap:
            if ts >= cutoff and price < min_price:
                min_price = price
                min_ts = ts
        if min_price == float('inf'):
            return None
        return (min_price, min_ts)

    def get_drop_percent(self, window_seconds: int) -> Optional[Tuple[float, float, float]]:
        """
        Calculate the maximum drop percentage in the given window.
        Returns (drop_percent, price_start, price_end) or None.
        """
        result = self.get_max_price_in_window(window_seconds)
        if result is None or self.current_price == 0:
            return None
        max_price, _ = result
        if max_price == 0:
            return None
        drop = ((max_price - self.current_price) / max_price) * 100
        return (drop, max_price, self.current_price)

    def get_pump_percent(self, window_seconds: int) -> Optional[Tuple[float, float, float]]:
        """
        Calculate the maximum pump percentage in the given window.
        Returns (pump_percent, price_start, price_end) or None.
        """
        result = self.get_min_price_in_window(window_seconds)
        if result is None or self.current_price == 0:
            return None
        min_price, _ = result
        if min_price == 0:
            return None
        pump = ((self.current_price - min_price) / min_price) * 100
        return (pump, min_price, self.current_price)


class CrashDetector:
    """Monitors prices and detects crashes."""

    def __init__(self, config: dict, database: Database, alert_manager: AlertManager,
                 trader: BinanceTrader = None):
        self.config = config
        self.db = database
        self.alerts = alert_manager
        self.trader = trader

        detection_cfg = config.get("detection", {})
        self.drop_threshold = detection_cfg.get("drop_threshold_percent", 30.0)
        self.pump_detection = detection_cfg.get("pump_detection", True)
        self.pump_threshold = detection_cfg.get("pump_threshold_percent", 5.0)
        self.pump_window_sec = detection_cfg.get("pump_window_seconds", 5)
        self.time_windows = detection_cfg.get("time_windows_minutes", [7, 15])
        self.max_window_seconds = max(self.time_windows) * 60 + 60  # Extra buffer

        trading_cfg = config.get("trading", {})
        self.trading_enabled = trading_cfg.get("enabled", True)
        self.trade_amount = trading_cfg.get("amount_per_trade_eur", 1000)
        self.take_profit = trading_cfg.get("take_profit_percent", 50.0)
        self.stop_loss = trading_cfg.get("stop_loss_percent", 20.0)
        self.max_simultaneous_trades = trading_cfg.get("max_simultaneous_trades", 0)
        self.max_duration_hours = trading_cfg.get("max_duration_hours", 0)
        self.trading_pairs_limit = config.get("binance", {}).get("top_pairs_count", 500)
        self._allowed_symbols: set = set()
        self.live_mode = trading_cfg.get("mode", "demo") == "live"
        self._forward_1111 = trading_cfg.get("mode", "demo") == "live_1111"

        # Price windows for each symbol
        self.windows: Dict[str, PriceWindow] = {}

        # Track which symbols had recent crash alerts (prevent duplicates)
        self._recent_crashes: Dict[str, float] = {}
        self._crash_cooldown = 300  # 5 min cooldown per symbol

        # Reversal detection
        self.reversal_mode = trading_cfg.get("reversal_mode", "instant")  # "instant" or "reversal"
        self.reversal_window_sec = trading_cfg.get("reversal_window_seconds", 30)
        self.reversal_timeout_sec = trading_cfg.get("reversal_timeout_seconds", 300)
        self._pending_reversals: Dict[str, dict] = {}  # symbol -> reversal tracking data

        # Double bottom confirmation
        self.double_bottom_enabled = trading_cfg.get("double_bottom_enabled", False)
        self.double_bottom_tolerance = trading_cfg.get("double_bottom_tolerance_percent", 3.0)
        self.double_bottom_lookback_days = trading_cfg.get("double_bottom_lookback_days", 120)
        self._double_bottom_cache: Dict[str, dict] = {}  # symbol -> {lows, timestamp}

        # Persistent start time (survives restarts)
        start_time_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".trading_start_time")
        try:
            with open(start_time_file, "r") as f:
                persistent_start = float(f.read().strip())
        except (FileNotFoundError, ValueError):
            persistent_start = time.time()
            with open(start_time_file, "w") as f:
                f.write(str(persistent_start))

        # Statistics
        self.stats = {
            "symbols_monitored": 0,
            "messages_received": 0,
            "crashes_detected": 0,
            "trades_opened": 0,
            "start_time": persistent_start,
            "last_message_time": 0,
            "ws_connected": False,
            "pending_reversals": 0,
            "entry_mode": self.reversal_mode
        }

    def update_allowed_symbols(self, sorted_symbols: list):
        """Update the set of symbols allowed for trading based on the pairs limit."""
        limit = self.trading_pairs_limit
        if limit > 0 and limit < len(sorted_symbols):
            self._allowed_symbols = set(s.upper() for s in sorted_symbols[:limit])
        else:
            self._allowed_symbols = set(s.upper() for s in sorted_symbols)
        logger.info(f"Trading allowed for {len(self._allowed_symbols)} symbols (limit: {limit})")

    def get_or_create_window(self, symbol: str) -> PriceWindow:
        """Get or create a price window for a symbol."""
        if symbol not in self.windows:
            self.windows[symbol] = PriceWindow(self.max_window_seconds)
        return self.windows[symbol]

    async def process_price(self, symbol: str, price: float):
        """Process a new price update for a symbol."""
        self.stats["messages_received"] += 1
        self.stats["last_message_time"] = time.time()
        self.stats["pending_reversals"] = len(self._pending_reversals)
        self.stats["entry_mode"] = self.reversal_mode

        window = self.get_or_create_window(symbol)
        window.add_price(price)

        # Check for crash in each time window
        for window_min in self.time_windows:
            window_sec = window_min * 60
            result = window.get_drop_percent(window_sec)
            if result is None:
                continue

            drop_percent, price_start, price_end = result

            if drop_percent >= self.drop_threshold:
                await self._handle_crash(
                    symbol, drop_percent, price_start, price_end,
                    window_min, window_sec
                )

        # Check for pump (buying power overwhelming - separate parameters)
        if self.pump_detection:
            pump_result = window.get_pump_percent(self.pump_window_sec)
            if pump_result is not None:
                pump_percent, pump_start, pump_end = pump_result
                if pump_percent >= self.pump_threshold:
                    pump_window_min = round(self.pump_window_sec / 60, 2)
                    await self._handle_crash(
                        symbol, pump_percent, pump_start, pump_end,
                        pump_window_min, self.pump_window_sec, is_pump=True
                    )

        # Check pending reversal confirmations
        if symbol in self._pending_reversals:
            await self._check_reversal(symbol, price)

        # Update open trades with current prices
        await self._update_open_trades(symbol, price)

    async def _handle_crash(self, symbol: str, drop_percent: float,
                            price_start: float, price_end: float,
                            time_window_min: int, window_seconds: float,
                            is_pump: bool = False):
        """Handle a detected crash or pump event."""
        if self._allowed_symbols and symbol.upper() not in self._allowed_symbols:
            return

        # Check cooldown
        now = time.time()
        last_crash = self._recent_crashes.get(symbol, 0)
        if now - last_crash < self._crash_cooldown:
            return

        # Skip if already have an open position for this symbol
        open_trades = self.db.get_open_trades()
        if any(t["symbol"] == symbol for t in open_trades):
            logger.info(f"SKIP: already have open position for {symbol}, ignoring new crash")
            return

        self._recent_crashes[symbol] = now
        self.stats["crashes_detected"] += 1

        signal_type = "PUMP" if is_pump else "CRASH"
        direction = "pumped" if is_pump else "dropped"
        logger.warning(
            f"{signal_type} DETECTED: {symbol} {direction} {drop_percent:.1f}% "
            f"in {time_window_min} minutes "
            f"(from {price_start:.8g} to {price_end:.8g})"
        )

        # Record in database
        crash_id = self.db.record_crash(
            symbol=symbol,
            price_start=price_start,
            price_end=price_end,
            drop_percent=drop_percent,
            time_window_min=time_window_min,
            window_seconds=window_seconds
        )

        # Fire alerts
        await self.alerts.fire_crash_alert(
            symbol, drop_percent, price_start, price_end, time_window_min
        )

        # Execute trade (paper or live)
        if self.trading_enabled:
            # Check double bottom (info only, does not block trades)
            if self.double_bottom_enabled:
                double_bottom = self._check_double_bottom(symbol, price_end)
                if double_bottom:
                    logger.warning(
                        f"DOUBLE BOTTOM CONFIRMED: {symbol} current {price_end:.8g} matches "
                        f"previous low {double_bottom['prev_low']:.8g} "
                        f"({double_bottom['days_ago']}d ago, {double_bottom['diff_pct']:.1f}% diff)"
                    )
                else:
                    logger.info(f"DOUBLE BOTTOM: No match for {symbol} (info only, trade continues)")

            if self.reversal_mode == "reversal":
                self._start_reversal_watch(crash_id, symbol, price_end)
            else:
                await self._execute_trade(crash_id, symbol, price_end)

    def _check_double_bottom(self, symbol: str, current_price: float) -> Optional[dict]:
        """Check if current price is near a previous historical low (double bottom)."""
        now = time.time()
        cache = self._double_bottom_cache.get(symbol)
        if cache and now - cache["timestamp"] < 3600:
            lows = cache["lows"]
        else:
            lows = self._fetch_historical_lows(symbol)
            self._double_bottom_cache[symbol] = {"lows": lows, "timestamp": now}

        if not lows:
            return None

        tolerance = self.double_bottom_tolerance / 100.0
        for low_price, low_ts in lows:
            diff_pct = abs(current_price - low_price) / low_price * 100
            if diff_pct <= self.double_bottom_tolerance:
                days_ago = int((now - low_ts) / 86400)
                if days_ago >= 3:
                    return {
                        "prev_low": low_price,
                        "days_ago": days_ago,
                        "diff_pct": diff_pct
                    }
        return None

    def _fetch_historical_lows(self, symbol: str) -> List[Tuple[float, float]]:
        """Fetch significant low points from the last N days of daily candles."""
        try:
            rest_url = self.config.get("binance", {}).get("rest_url", "https://api.binance.com")
            resp = requests.get(f"{rest_url}/api/v3/klines", params={
                "symbol": symbol, "interval": "1d",
                "limit": self.double_bottom_lookback_days
            }, timeout=10)
            klines = resp.json()
            if not klines or not isinstance(klines, list):
                return []

            # Find local minimums (low points where neighbors are higher)
            lows = []
            prices = [(float(k[3]), k[0] / 1000) for k in klines]  # (low, timestamp)
            for i in range(1, len(prices) - 1):
                if prices[i][0] <= prices[i-1][0] and prices[i][0] <= prices[i+1][0]:
                    lows.append(prices[i])
            # Also include the absolute minimum
            if prices:
                abs_min = min(prices, key=lambda x: x[0])
                if abs_min not in lows:
                    lows.append(abs_min)

            return lows
        except Exception as e:
            logger.debug(f"Failed to fetch historical lows for {symbol}: {e}")
            return []

    def _start_reversal_watch(self, crash_id: int, symbol: str, crash_price: float):
        """Start monitoring buy/sell pressure for reversal confirmation."""
        if symbol in self._pending_reversals:
            return
        now = time.time()
        self._pending_reversals[symbol] = {
            "crash_id": crash_id,
            "crash_price": crash_price,
            "start_time": now,
            "timeout": now + self.reversal_timeout_sec,
            "buy_volume": 0.0,
            "sell_volume": 0.0,
            "price_low": crash_price,
            "last_price": crash_price,
            "higher_lows": 0,
            "window_prices": [],
            "confirmed": False
        }
        logger.info(
            f"REVERSAL WATCH: {symbol} @ {crash_price:.8g} - "
            f"waiting for buy pressure confirmation (timeout {self.reversal_timeout_sec}s)"
        )

    async def _check_reversal(self, symbol: str, price: float):
        """Check if pending reversal conditions are met for a symbol."""
        if symbol not in self._pending_reversals:
            return
        rev = self._pending_reversals[symbol]
        now = time.time()

        if now > rev["timeout"]:
            logger.info(f"REVERSAL TIMEOUT: {symbol} - no confirmation, skipping trade")
            del self._pending_reversals[symbol]
            return

        # Track price for higher-low detection
        rev["window_prices"].append((now, price))
        rev["last_price"] = price

        if price < rev["price_low"]:
            rev["price_low"] = price

        # Clean old entries from window
        cutoff = now - self.reversal_window_sec
        rev["window_prices"] = [(t, p) for t, p in rev["window_prices"] if t >= cutoff]

        if len(rev["window_prices"]) < 3:
            return

        # Split window in half to detect higher lows
        mid = len(rev["window_prices"]) // 2
        first_half = rev["window_prices"][:mid]
        second_half = rev["window_prices"][mid:]

        if first_half and second_half:
            first_low = min(p for _, p in first_half)
            second_low = min(p for _, p in second_half)
            second_high = max(p for _, p in second_half)

            # Reversal confirmed when:
            # 1) Second half low is higher than first half low (higher low)
            # 2) Current price is above the crash price (bouncing)
            # 3) Price has risen at least 1% from the lowest point
            bounce_pct = ((price - rev["price_low"]) / rev["price_low"]) * 100 if rev["price_low"] > 0 else 0

            if second_low > first_low and price > rev["crash_price"] and bounce_pct >= 1.0:
                logger.warning(
                    f"REVERSAL CONFIRMED: {symbol} bounce {bounce_pct:.1f}% from low "
                    f"({rev['price_low']:.8g} -> {price:.8g}), higher lows detected"
                )
                crash_id = rev["crash_id"]
                del self._pending_reversals[symbol]
                await self._execute_trade(crash_id, symbol, price)

    async def _execute_trade(self, crash_id: int, symbol: str, price: float):
        """Execute a buy trade (paper or live depending on mode)."""
        open_trades = self.db.get_open_trades()
        if any(t["symbol"] == symbol for t in open_trades):
            logger.info(f"SKIP DUPLICATE: already have open position for {symbol}")
            return
        if self.max_simultaneous_trades > 0:
            if len(open_trades) >= self.max_simultaneous_trades:
                logger.info(
                    f"MAX TRADES REACHED: {len(open_trades)}/{self.max_simultaneous_trades} "
                    f"open - skipping {symbol}"
                )
                return
        if self.live_mode and self.trader and self.trader.live_mode:
            result = self.trader.market_buy(symbol, self.trade_amount)
            if result:
                _cur_tp = self.pump_tp if self.pump_only else self.take_profit
                _cur_sl = self.pump_sl if self.pump_only else self.stop_loss
                trade_id = self.db.record_trade(
                    crash_id=crash_id,
                    symbol=symbol,
                    entry_price=result["avg_price"],
                    quantity=result["filled_qty"],
                    amount_eur=result["filled_quote"],
                    is_live=True,
                    order_id=str(result["order_id"]),
                    tp_pct=_cur_tp,
                    sl_pct=_cur_sl,
                    max_dur_hours=self.max_duration_hours if self.max_duration_hours > 0 else None,
                    trade_mode="live"
                )
                self.stats["trades_opened"] += 1
                logger.info(
                    f"LIVE TRADE: BUY {result['filled_qty']:.8g} {symbol} "
                    f"@ {result['avg_price']:.8g} for {result['filled_quote']:.2f} USDT "
                    f"[Trade #{trade_id}]"
                )
                await self.alerts.fire_trade_update(
                    symbol, 0, result["filled_quote"], "LIVE BUY"
                )
            else:
                logger.error(f"LIVE TRADE FAILED for {symbol}, recording as paper trade")
                self._record_paper_trade(crash_id, symbol, price)
        else:
            self._record_paper_trade(crash_id, symbol, price)

    def _record_paper_trade(self, crash_id: int, symbol: str, price: float):
        """Record a simulated buy trade."""
        quantity = self.trade_amount / price
        _cur_tp = self.pump_tp if self.pump_only else self.take_profit
        _cur_sl = self.pump_sl if self.pump_only else self.stop_loss
        trade_id = self.db.record_trade(
            crash_id=crash_id,
            symbol=symbol,
            entry_price=price,
            quantity=quantity,
            amount_eur=self.trade_amount,
            tp_pct=_cur_tp,
            sl_pct=_cur_sl,
            max_dur_hours=self.max_duration_hours if self.max_duration_hours > 0 else None,
            trade_mode="demo"
        )
        self.stats["trades_opened"] += 1
        logger.info(
            f"PAPER TRADE: BUY {quantity:.8g} {symbol} @ {price:.8g} "
            f"(EUR {self.trade_amount}) [Trade #{trade_id}]"
        )

    def _forward_to_1111(self, symbol, price):
        try:
            import requests as _req
            resp = _req.post(
                "http://127.0.0.1:1111/api/signal",
                json={"symbol": symbol, "volume_ratio": 3.0, "ob_ratio": 1.5, "price": price, "source_port": 5055},
                auth=("admin", "guidoleb@@11"),
                timeout=3
            )
            logger.info(f"FORWARDED to 1111: {symbol} @ {price} -> {resp.status_code}")
        except Exception as e:
            logger.warning(f"FORWARD ERROR to 1111: {symbol} - {e}")

    async def _update_open_trades(self, symbol: str, current_price: float):
        """Update P&L for open trades matching this symbol."""
        open_trades = self.db.get_open_trades()
        for trade in open_trades:
            if trade["symbol"] != symbol:
                continue

            self.db.update_trade_price(trade["id"], current_price)

            # Check take-profit / stop-loss
            entry_price = trade["entry_price"]
            pnl_percent = ((current_price - entry_price) / entry_price) * 100

            if pnl_percent >= self.take_profit:
                await self._close_trade(trade, current_price, pnl_percent, "TAKE PROFIT")
            elif pnl_percent <= -self.stop_loss:
                await self._close_trade(trade, current_price, pnl_percent, "STOP LOSS")
            elif (trade.get("max_dur_hours") or self.max_duration_hours) > 0:
                _dur_limit = trade.get("max_dur_hours") or self.max_duration_hours
                elapsed_hours = (time.time() - trade["entry_time"]) / 3600
                if elapsed_hours >= _dur_limit:
                    await self._close_trade(trade, current_price, pnl_percent, "MAX DURATION")


    async def _close_trade(self, trade: dict, current_price: float,
                           pnl_percent: float, reason: str):
        """Close a trade (paper or live)."""
        symbol = trade["symbol"]
        is_live = trade.get("is_live", False)

        if is_live and self.live_mode and self.trader and self.trader.live_mode:
            result = self.trader.market_sell(symbol, trade["quantity"])
            if result:
                self.db.close_trade(trade["id"], result["avg_price"])
                actual_pnl = ((result["avg_price"] - trade["entry_price"]) / trade["entry_price"]) * 100
                logger.info(
                    f"LIVE {reason}: {symbol} sold {result['filled_qty']} "
                    f"@ {result['avg_price']:.8g} ({actual_pnl:+.1f}%)"
                )
            else:
                logger.error(f"LIVE SELL FAILED for {symbol} - keeping position open")
                return
        else:
            self.db.close_trade(trade["id"], current_price)
            logger.info(
                f"{reason}: {symbol} closed at {pnl_percent:+.1f}% "
                f"({current_price:.8g})"
            )

        await self.alerts.fire_trade_update(
            symbol, pnl_percent,
            trade["amount_eur"] * pnl_percent / 100,
            reason
        )


class BinanceMonitor:
    """Manages connection to Binance WebSocket and feeds data to CrashDetector."""

    def __init__(self, config: dict, detector: CrashDetector):
        self.config = config
        self.detector = detector

        binance_cfg = config.get("binance", {})
        self.rest_url = binance_cfg.get("rest_url", "https://api.binance.com")
        self.ws_url = binance_cfg.get("ws_url", "wss://stream.binance.com:9443/ws")
        self.top_pairs_count = binance_cfg.get("top_pairs_count", 500)
        self.quote_asset = binance_cfg.get("quote_asset", "USDT")

        self.symbols: List[str] = []
        self._running = False
        self._ws_tasks: List[asyncio.Task] = []

    def fetch_top_pairs(self) -> List[str]:
        """Fetch top trading pairs - from shared cache first, Binance REST as fallback."""
        import sys
        if "/opt/crypto-shared" not in sys.path:
            sys.path.insert(0, "/opt/crypto-shared")
        try:
            from shared_reader import get_top_pairs
            cached = get_top_pairs(self.top_pairs_count)
            if cached:
                self.symbols = cached[:self.top_pairs_count]
                logger.info(f"Loaded {len(self.symbols)} pairs from shared cache")
                self.detector.stats["symbols_monitored"] = len(self.symbols)
                self.detector.update_allowed_symbols(self.symbols)
                return self.symbols
        except Exception as e:
            logger.debug(f"Shared cache unavailable: {e}")
        return self._fetch_top_pairs_binance()

    def _fetch_top_pairs_binance(self) -> List[str]:
        logger.info(f"Fetching top {self.top_pairs_count} {self.quote_asset} pairs...")

        try:
            # Get 24hr ticker data
            url = f"{self.rest_url}/api/v3/ticker/24hr"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            tickers = response.json()

            # Filter USDT pairs and sort by quote volume
            usdt_pairs = [
                t for t in tickers
                if t["symbol"].endswith(self.quote_asset)
                and float(t["quoteVolume"]) > 0
            ]

            # Sort by 24h quote volume (descending)
            usdt_pairs.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)

            # Take top N
            top = usdt_pairs[:self.top_pairs_count]
            self.symbols = [t["symbol"].lower() for t in top]

            logger.info(
                f"Found {len(self.symbols)} {self.quote_asset} pairs. "
                f"Top 5: {[s.upper() for s in self.symbols[:5]]}"
            )
            self.detector.stats["symbols_monitored"] = len(self.symbols)
            self.detector.update_allowed_symbols(self.symbols)
            return self.symbols

        except Exception as e:
            logger.error(f"Failed to fetch pairs from Binance: {e}")
            # Fallback to common pairs
            self.symbols = [
                "btcusdt", "ethusdt", "bnbusdt", "solusdt", "xrpusdt",
                "dogeusdt", "adausdt", "avaxusdt", "dotusdt", "maticusdt"
            ]
            logger.info(f"Using fallback list of {len(self.symbols)} pairs")
            self.detector.stats["symbols_monitored"] = len(self.symbols)
            return self.symbols

    def preload_prices(self):
        """Preload recent price data from Binance klines so Top Drops works immediately."""
        try:
            _check = requests.get(f"{self.rest_url}/api/v3/time", timeout=3)
            if _check.status_code == 418:
                logger.warning("Binance rate limited (418) - skipping preload, will use WebSocket data")
                return
        except Exception:
            pass
        from concurrent.futures import ThreadPoolExecutor, as_completed
        max_window = self.detector.max_window_seconds
        interval = "1m"
        limit = min(max_window // 60 + 5, 120)
        logger.info(f"Preloading {limit} minutes of price history for {len(self.symbols)} pairs...")

        def fetch_klines(symbol):
            try:
                resp = requests.get(f"{self.rest_url}/api/v3/klines", params={
                    "symbol": symbol.upper(), "interval": interval, "limit": limit
                }, timeout=10)
                klines = resp.json()
                if not klines or not isinstance(klines, list):
                    return symbol, []
                return symbol, klines
            except Exception:
                return symbol, []

        loaded = 0
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(fetch_klines, s): s for s in self.symbols}
            for future in as_completed(futures):
                symbol, klines = future.result()
                if klines:
                    window = self.detector.get_or_create_window(symbol.upper())
                    for k in klines:
                        ts = k[0] / 1000
                        close = float(k[4])
                        high = float(k[2])
                        low = float(k[3])
                        window.add_price(high, ts)
                        window.add_price(low, ts + 0.001)
                        window.add_price(close, ts + 0.002)
                    loaded += 1

        logger.info(f"Preloaded price history for {loaded}/{len(self.symbols)} pairs")
        self.detector.stats["symbols_monitored"] = len(self.symbols)

    async def start(self):
        """Start monitoring WebSocket streams."""
        if not self.symbols:
            self.fetch_top_pairs()

        self.preload_prices()

        self._running = True
        logger.info("Starting Binance WebSocket monitor...")

        # Binance allows max 1024 streams per connection
        # Split into batches of ~200 for stability
        batch_size = 200
        batches = [
            self.symbols[i:i + batch_size]
            for i in range(0, len(self.symbols), batch_size)
        ]

        logger.info(f"Connecting {len(batches)} WebSocket streams...")

        tasks = []
        for i, batch in enumerate(batches):
            task = asyncio.create_task(self._run_stream(batch, i))
            tasks.append(task)
            self._ws_tasks.append(task)

        # Wait for all streams
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_stream(self, symbols: List[str], batch_id: int):
        """Run a single WebSocket stream for a batch of symbols."""
        # Create combined stream URL
        streams = [f"{s}@miniTicker" for s in symbols]
        stream_name = "/".join(streams)
        url = f"wss://stream.binance.com:9443/stream?streams={stream_name}"

        while self._running:
            try:
                logger.info(
                    f"Batch {batch_id}: Connecting to {len(symbols)} streams..."
                )
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                    max_size=2**20
                ) as ws:
                    self.detector.stats["ws_connected"] = True
                    logger.info(f"Batch {batch_id}: Connected successfully")

                    async for message in ws:
                        if not self._running:
                            break
                        try:
                            data = json.loads(message)
                            # Combined stream format: {"stream": "...", "data": {...}}
                            if "data" in data:
                                ticker = data["data"]
                            else:
                                ticker = data

                            symbol = ticker.get("s", "").upper()
                            close_price = float(ticker.get("c", 0))

                            if symbol and close_price > 0:
                                await self.detector.process_price(symbol, close_price)

                        except (json.JSONDecodeError, KeyError, ValueError) as e:
                            logger.debug(f"Parse error: {e}")
                            continue

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(
                    f"Batch {batch_id}: WebSocket closed ({e.code}), reconnecting..."
                )
                self.detector.stats["ws_connected"] = False
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(
                    f"Batch {batch_id}: WebSocket error: {e}, reconnecting..."
                )
                self.detector.stats["ws_connected"] = False
                await asyncio.sleep(10)

    def stop(self):
        """Stop all WebSocket connections."""
        self._running = False
        for task in self._ws_tasks:
            task.cancel()
        logger.info("Monitor stopped")


def run_monitor(config: dict, database: Database, alert_manager: AlertManager,
                detector_ref: list):
    """Run the monitor in its own thread with its own event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    trader = BinanceTrader(config)
    detector = CrashDetector(config, database, alert_manager, trader)
    monitor = BinanceMonitor(config, detector)

    # Store reference for dashboard access
    detector_ref.clear()
    detector_ref.append(detector)
    detector_ref.append(monitor)

    try:
        monitor.fetch_top_pairs()
        loop.run_until_complete(monitor.start())
    except KeyboardInterrupt:
        monitor.stop()
    except Exception as e:
        logger.error(f"Monitor thread error: {e}")
    finally:
        loop.close()
