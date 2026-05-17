import asyncio
import json
import os
import time
import logging
import threading
from collections import deque
from typing import Dict, List, Optional

import requests
import websockets

logger = logging.getLogger(__name__)


class PriceWindow:
    def __init__(self, symbol, max_minutes=60):
        self.symbol = symbol
        self.current_price = 0.0
        self.prices = deque(maxlen=max_minutes * 60)

    def update(self, price):
        self.current_price = price
        self.prices.append((time.time(), price))


class MultiStrategyDetector:
    def __init__(self, config, strategy_manager):
        self.config = config
        self.strategy_manager = strategy_manager
        detection_cfg = config.get("detection", {})
        self.volume_pump_mode = detection_cfg.get("volume_pump_mode", True)
        self.base_volume_spike = detection_cfg.get("volume_spike_multiplier", 3.0)
        self.base_ob_ratio = detection_cfg.get("orderbook_buy_ratio", 1.5)
        self.ob_check_seconds = detection_cfg.get("orderbook_check_seconds", 5)
        self._candle_volumes: Dict[str, deque] = {}
        self._ob_cooldown: Dict[str, float] = {}
        self._rest_url = config.get("binance", {}).get("rest_url", "https://api.binance.com")
        self.trading_pairs_limit = config.get("binance", {}).get("top_pairs_count", 300)
        self.windows: Dict[str, PriceWindow] = {}
        self.stats = {
            "ws_connected": False,
            "symbols_monitored": 0,
            "pumps_detected": 0,
            "trades_opened": 0
        }

    async def process_price(self, symbol, price):
        if symbol not in self.windows:
            self.windows[symbol] = PriceWindow(symbol)
        self.windows[symbol].update(price)
        self.strategy_manager.check_all_exits(self._get_prices())

    def _get_prices(self):
        return {s: w.current_price for s, w in self.windows.items() if w.current_price > 0}

    async def process_kline(self, symbol, kline):
        if not self.volume_pump_mode:
            return
        is_closed = kline.get("x", False)
        if not is_closed:
            return
        quote_volume = float(kline.get("q", 0))
        if symbol not in self._candle_volumes:
            self._candle_volumes[symbol] = deque(maxlen=21)
        self._candle_volumes[symbol].append(quote_volume)
        volumes = self._candle_volumes[symbol]
        if len(volumes) < 21:
            return
        prev_volumes = list(volumes)[:-1]
        avg_volume = sum(prev_volumes) / len(prev_volumes)
        current_volume = volumes[-1]
        if avg_volume <= 0:
            return
        min_spike = min(s.volume_spike for s in self.strategy_manager.strategies.values() if s.active) if any(s.active for s in self.strategy_manager.strategies.values()) else self.base_volume_spike
        ratio = current_volume / avg_volume
        if ratio >= min_spike:
            now = time.time()
            last_check = self._ob_cooldown.get(symbol, 0)
            if now - last_check < 300:
                return
            self._ob_cooldown[symbol] = now
            close_price = float(kline.get("c", 0))
            logger.warning(f"VOLUME SPIKE: {symbol} {ratio:.1f}x avg, checking order book...")
            asyncio.ensure_future(self._check_orderbook(symbol, close_price, ratio))

    async def _check_orderbook(self, symbol, trigger_price, volume_ratio):
        import aiohttp
        deadline = time.time() + self.ob_check_seconds
        try:
            async with aiohttp.ClientSession() as session:
                while time.time() < deadline:
                    try:
                        url = f"{self._rest_url}/api/v3/depth"
                        async with session.get(url, params={"symbol": symbol, "limit": 20}, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                            data = await resp.json()
                        bids = data.get("bids", [])
                        asks = data.get("asks", [])
                        buy_total = sum(float(b[0]) * float(b[1]) for b in bids)
                        sell_total = sum(float(a[0]) * float(a[1]) for a in asks)
                        if sell_total > 0:
                            ob_ratio = buy_total / sell_total
                            min_ob = min(s.ob_ratio for s in self.strategy_manager.strategies.values() if s.active) if any(s.active for s in self.strategy_manager.strategies.values()) else self.base_ob_ratio
                            if ob_ratio >= min_ob:
                                w = self.windows.get(symbol)
                                price = w.current_price if w else trigger_price
                                logger.warning(f"PUMP CONFIRMED: {symbol} vol={volume_ratio:.1f}x ob={ob_ratio:.2f}")
                                self.stats["pumps_detected"] += 1
                                n = self.strategy_manager.dispatch_signal(symbol, volume_ratio, ob_ratio, price)
                                self.stats["trades_opened"] += n
                                return
                    except Exception as e:
                        logger.debug(f"OB check error {symbol}: {e}")
                    await asyncio.sleep(1)
            logger.info(f"PUMP REJECTED: {symbol} - OB not confirmed")
        except Exception as e:
            logger.error(f"OB loop error {symbol}: {e}")


class MultiStrategyMonitor:
    def __init__(self, config, detector):
        self.config = config
        self.detector = detector
        self._running = True
        self._ws_tasks = []
        self._symbols = []

    def fetch_top_pairs(self):
        rest_url = self.config.get("binance", {}).get("rest_url", "https://api.binance.com")
        limit = self.config.get("binance", {}).get("top_pairs_count", 300)
        quote = self.config.get("binance", {}).get("quote_asset", "USDT")
        try:
            resp = requests.get(f"{rest_url}/api/v3/ticker/24hr", timeout=15)
            tickers = resp.json()
            usdt_pairs = [t for t in tickers if t["symbol"].endswith(quote) and float(t["quoteVolume"]) > 0]
            usdt_pairs.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)
            self._symbols = [t["symbol"].lower() for t in usdt_pairs[:limit]]
            self.detector.stats["symbols_monitored"] = len(self._symbols)
            logger.info(f"Fetched {len(self._symbols)} trading pairs")
        except Exception as e:
            logger.error(f"Failed to fetch pairs: {e}")

    async def start(self):
        if not self._symbols:
            self.fetch_top_pairs()
        batch_size = 50
        batches = [self._symbols[i:i+batch_size] for i in range(0, len(self._symbols), batch_size)]
        logger.info(f"Starting {len(batches)} WebSocket streams...")
        tasks = []
        for i, batch in enumerate(batches):
            task = asyncio.create_task(self._run_stream(batch, i))
            tasks.append(task)
            self._ws_tasks.append(task)
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_stream(self, symbols, batch_id):
        streams = [f"{s}@miniTicker" for s in symbols]
        if self.detector.volume_pump_mode:
            streams += [f"{s}@kline_1m" for s in symbols]
        stream_name = "/".join(streams)
        url = f"wss://stream.binance.com:9443/stream?streams={stream_name}"
        while self._running:
            try:
                logger.info(f"Batch {batch_id}: Connecting {len(symbols)} streams...")
                async with websockets.connect(url, ping_interval=20, ping_timeout=10, close_timeout=5, max_size=2**20) as ws:
                    self.detector.stats["ws_connected"] = True
                    logger.info(f"Batch {batch_id}: Connected")
                    async for message in ws:
                        if not self._running:
                            break
                        try:
                            data = json.loads(message)
                            ticker = data.get("data", data)
                            event_type = ticker.get("e", "")
                            if event_type == "kline":
                                kline = ticker.get("k", {})
                                symbol = kline.get("s", "").upper()
                                if symbol:
                                    await self.detector.process_kline(symbol, kline)
                            else:
                                symbol = ticker.get("s", "").upper()
                                close_price = float(ticker.get("c", 0))
                                if symbol and close_price > 0:
                                    await self.detector.process_price(symbol, close_price)
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue
            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"Batch {batch_id}: WS closed, reconnecting...")
                self.detector.stats["ws_connected"] = False
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Batch {batch_id}: WS error: {e}")
                self.detector.stats["ws_connected"] = False
                await asyncio.sleep(10)

    def stop(self):
        self._running = False
        for t in self._ws_tasks:
            t.cancel()


def run_monitor(config, strategy_manager, detector_ref):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    detector = MultiStrategyDetector(config, strategy_manager)
    monitor = MultiStrategyMonitor(config, detector)
    detector_ref.clear()
    detector_ref.append(detector)
    detector_ref.append(monitor)
    try:
        monitor.fetch_top_pairs()
        loop.run_until_complete(monitor.start())
    except Exception as e:
        logger.error(f"Monitor error: {e}")
    finally:
        loop.close()
