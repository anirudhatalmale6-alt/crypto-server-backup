import time
import json
import os
import logging

logger = logging.getLogger(__name__)


class Strategy:
    def __init__(self, strategy_id, config, db, trader=None):
        self.id = strategy_id
        self.db = db
        self.trader = trader
        self.name = config.get("name", strategy_id)
        self.active = config.get("active", False)
        self.tp = config.get("tp_percent", 50.0)
        self.sl = config.get("sl_percent", 20.0)
        self.trade_amount = config.get("trade_amount", 10.0)
        self.pump_tp = config.get("pump_tp_percent", 30.0)
        self.pump_sl = config.get("pump_sl_percent", 10.0)
        self.max_trades = config.get("max_trades", 100)
        self.max_duration = config.get("max_duration_hours", 2.0) * 3600
        self.volume_spike = config.get("volume_spike_multiplier", 3.0)
        self.ob_ratio = config.get("orderbook_buy_ratio", 1.5)
        self.pump_window = config.get("pump_window_seconds", 600)
        self._cooldowns = {}
        self._start_time = None

    def start(self):
        self.active = True
        self._start_time = time.time()
        self.db.set_strategy_active(self.id, True)
        logger.info(f"Strategy {self.id} STARTED")

    def stop(self):
        self.active = False
        self.db.set_strategy_active(self.id, False)
        logger.info(f"Strategy {self.id} STOPPED")

    def get_config(self):
        return {
            "tp_percent": self.tp,
            "sl_percent": self.sl,
            "trade_amount": self.trade_amount,
            "pump_tp_percent": self.pump_tp,
            "pump_sl_percent": self.pump_sl,
            "max_trades": self.max_trades,
            "max_duration_hours": round(self.max_duration / 3600, 1),
            "volume_spike_multiplier": self.volume_spike,
            "orderbook_buy_ratio": self.ob_ratio,
            "pump_window_seconds": self.pump_window,
            "active": self.active,
            "name": self.name
        }

    def update_config(self, cfg):
        if "tp_percent" in cfg: self.tp = float(cfg["tp_percent"])
        if "sl_percent" in cfg: self.sl = float(cfg["sl_percent"])
        if "trade_amount" in cfg: self.trade_amount = float(cfg["trade_amount"])
        if "pump_tp_percent" in cfg: self.pump_tp = float(cfg["pump_tp_percent"])
        if "pump_sl_percent" in cfg: self.pump_sl = float(cfg["pump_sl_percent"])
        if "max_trades" in cfg: self.max_trades = int(cfg["max_trades"])
        if "max_duration_hours" in cfg: self.max_duration = float(cfg["max_duration_hours"]) * 3600
        if "volume_spike_multiplier" in cfg: self.volume_spike = float(cfg["volume_spike_multiplier"])
        if "orderbook_buy_ratio" in cfg: self.ob_ratio = float(cfg["orderbook_buy_ratio"])
        if "pump_window_seconds" in cfg: self.pump_window = int(cfg["pump_window_seconds"])
        if "name" in cfg: self.name = cfg["name"]
        self.db.save_strategy(self.id, self.name, self.get_config(), self.active)
        self._save_to_file()

    def _save_to_file(self):
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        try:
            with open(cfg_path, "r") as f:
                full_cfg = json.load(f)
            full_cfg["strategies"][self.id] = self.get_config()
            with open(cfg_path, "w") as f:
                json.dump(full_cfg, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save strategy config: {e}")

    def evaluate_signal(self, symbol, volume_ratio, ob_ratio, price):
        if not self.active:
            return False
        now = time.time()
        last = self._cooldowns.get(symbol, 0)
        if now - last < 300:
            return False
        open_trades = self.db.get_open_trades(self.id)
        if len(open_trades) >= self.max_trades:
            return False
        if any(t["symbol"] == symbol for t in open_trades):
            return False
        if volume_ratio < self.volume_spike:
            return False
        if ob_ratio < self.ob_ratio:
            return False
        self._cooldowns[symbol] = now
        if self.trader and self.trader.live_mode:
            result = self.trader.market_buy(symbol, self.trade_amount)
            if result:
                trade_id = self.db.record_trade(self.id, symbol, result["avg_price"], result["filled_qty"], result["filled_quote"], is_live=True, order_id=str(result["order_id"]), trade_mode="live_1111")
                logger.info(f"[{self.id}] LIVE BUY {result['filled_qty']:.8g} {symbol} @ {result['avg_price']:.8g} ({result['filled_quote']:.2f} USDC) [#{trade_id}]")
                try:
                    import requests as _rq
                    _asset = symbol.replace("USDT", "").replace("USDC", "")
                    _rq.post("http://127.0.0.1:5065/api/internal/add-position",
                        json={"coin": _asset, "quantity": result["filled_qty"],
                              "entry_price": result["avg_price"], "tp_pct": 50, "sl_pct": 20},
                        timeout=3)
                except Exception:
                    pass
            else:
                quantity = self.trade_amount / price
                trade_id = self.db.record_trade(self.id, symbol, price, quantity, self.trade_amount, trade_mode="demo")
                logger.warning(f"[{self.id}] LIVE BUY FAILED {symbol}, recorded as paper [#{trade_id}]")
        else:
            quantity = self.trade_amount / price
            trade_id = self.db.record_trade(self.id, symbol, price, quantity, self.trade_amount, trade_mode="demo")
            logger.info(f"[{self.id}] DEMO BUY {quantity:.8g} {symbol} @ {price:.8g} ({self.trade_amount} USDC) [#{trade_id}]")
        return True

    def check_exits(self, current_prices):
        open_trades = self.db.get_open_trades(self.id)
        for t in open_trades:
            symbol = t["symbol"]
            price = current_prices.get(symbol)
            if not price:
                continue
            self.db.update_trade_price(t["id"], price)
            pnl_pct = ((price - t["entry_price"]) / t["entry_price"]) * 100
            age = time.time() - t["entry_time"]
            tp = self.pump_tp
            sl = self.pump_sl
            if pnl_pct >= tp:
                if self.trader and t.get("is_live"):
                    sell_result = self.trader.market_sell(symbol, t["quantity"])
                    if sell_result:
                        price = sell_result["avg_price"]
                        logger.info(f"[{self.id}] LIVE TP SELL: {symbol} +{pnl_pct:.1f}% @ {price:.8g}")
                self.db.close_trade(t["id"], price, "TP")
                logger.info(f"[{self.id}] TP: {symbol} +{pnl_pct:.1f}% @ {price:.8g}")
            elif pnl_pct <= -sl:
                if self.trader and t.get("is_live"):
                    sell_result = self.trader.market_sell(symbol, t["quantity"])
                    if sell_result:
                        price = sell_result["avg_price"]
                        logger.info(f"[{self.id}] LIVE SL SELL: {symbol} {pnl_pct:.1f}% @ {price:.8g}")
                self.db.close_trade(t["id"], price, "SL")
                logger.info(f"[{self.id}] SL: {symbol} {pnl_pct:.1f}% @ {price:.8g}")
            elif age >= self.max_duration:
                if self.trader and t.get("is_live"):
                    sell_result = self.trader.market_sell(symbol, t["quantity"])
                    if sell_result:
                        price = sell_result["avg_price"]
                        logger.info(f"[{self.id}] LIVE TIMEOUT SELL: {symbol} {pnl_pct:.1f}% @ {price:.8g}")
                self.db.close_trade(t["id"], price, "TIMEOUT")
                logger.info(f"[{self.id}] TIMEOUT: {symbol} {pnl_pct:.1f}% @ {price:.8g}")


class StrategyManager:
    def __init__(self, db, trader=None):
        self.strategies = {}
        self.trader = trader
        self.db = db

    def register(self, strategy_id, config):
        s = Strategy(strategy_id, config, self.db, self.trader)
        self.strategies[strategy_id] = s
        self.db.save_strategy(strategy_id, s.name, s.get_config(), s.active)
        return s

    def dispatch_signal(self, symbol, volume_ratio, ob_ratio, price):
        trades_opened = 0
        for s in self.strategies.values():
            if s.evaluate_signal(symbol, volume_ratio, ob_ratio, price):
                trades_opened += 1
        return trades_opened

    def check_all_exits(self, current_prices):
        for s in self.strategies.values():
            if s.active:
                s.check_exits(current_prices)

    def get_strategy(self, strategy_id):
        return self.strategies.get(strategy_id)

    def get_all_status(self):
        result = {}
        for sid, s in self.strategies.items():
            stats = self.db.get_strategy_stats(sid)
            result[sid] = {
                "config": s.get_config(),
                "stats": stats,
                "active": s.active
            }
        return result
