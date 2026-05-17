import sqlite3
import threading
import time
import json
import os
import logging

logger = logging.getLogger(__name__)


class MultiStrategyDatabase:
    def __init__(self, db_path="multi_strategy.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self):
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    def _init_db(self):
        conn = self._get_conn()
        with self._lock:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS strategies (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    config TEXT NOT NULL,
                    active INTEGER DEFAULT 0,
                    created_at REAL
                );
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL DEFAULT 'BUY',
                    entry_price REAL NOT NULL,
                    current_price REAL,
                    quantity REAL NOT NULL,
                    amount_usdc REAL NOT NULL,
                    entry_time REAL NOT NULL,
                    entry_time_str TEXT NOT NULL,
                    exit_price REAL,
                    exit_time REAL,
                    exit_time_str TEXT,
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    pnl_usdc REAL DEFAULT 0.0,
                    pnl_percent REAL DEFAULT 0.0,
                    close_reason TEXT,
                    entry_type TEXT DEFAULT 'pump'
                );
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    volume_ratio REAL,
                    orderbook_ratio REAL,
                    price REAL,
                    timestamp REAL
                );
                CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_id);
                CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
                CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
                CREATE INDEX IF NOT EXISTS idx_signals_time ON signals(timestamp);
            """)
            conn.commit()

    def save_strategy(self, strategy_id, name, config, active=False):
        conn = self._get_conn()
        with self._lock:
            conn.execute("""
                INSERT OR REPLACE INTO strategies (id, name, config, active, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (strategy_id, name, json.dumps(config), 1 if active else 0, time.time()))
            conn.commit()

    def get_strategy(self, strategy_id):
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM strategies WHERE id=?", (strategy_id,)).fetchone()
        if row:
            d = dict(row)
            d["config"] = json.loads(d["config"])
            return d
        return None

    def set_strategy_active(self, strategy_id, active):
        conn = self._get_conn()
        with self._lock:
            conn.execute("UPDATE strategies SET active=? WHERE id=?", (1 if active else 0, strategy_id))
            conn.commit()

    def record_trade(self, strategy_id, symbol, entry_price, quantity, amount_usdc, is_live=False, order_id=None, tp_pct=None, sl_pct=None, max_dur_hours=None, trade_mode=None):
        now = time.time()
        now_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
        conn = self._get_conn()
        with self._lock:
            cursor = conn.execute("""
                INSERT INTO trades
                (strategy_id, symbol, entry_price, current_price, quantity, amount_usdc,
                 entry_time, entry_time_str, status, entry_type, is_live, order_id, tp_pct, sl_pct, max_dur_hours, trade_mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', 'pump', ?, ?, ?, ?, ?, ?)
            """, (strategy_id, symbol, entry_price, entry_price, quantity, amount_usdc, now, now_str, 1 if is_live else 0, order_id, tp_pct, sl_pct, max_dur_hours, trade_mode))
            conn.commit()
            return cursor.lastrowid

    def update_trade_price(self, trade_id, current_price):
        conn = self._get_conn()
        with self._lock:
            row = conn.execute(
                "SELECT entry_price, quantity, amount_usdc FROM trades WHERE id=?", (trade_id,)
            ).fetchone()
            if row:
                pnl_usdc = row["quantity"] * current_price - row["amount_usdc"]
                pnl_pct = ((current_price - row["entry_price"]) / row["entry_price"]) * 100
                conn.execute(
                    "UPDATE trades SET current_price=?, pnl_usdc=?, pnl_percent=? WHERE id=?",
                    (current_price, pnl_usdc, pnl_pct, trade_id))
                conn.commit()

    def close_trade(self, trade_id, exit_price, reason="MANUAL"):
        now = time.time()
        now_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
        conn = self._get_conn()
        with self._lock:
            row = conn.execute(
                "SELECT entry_price, quantity, amount_usdc FROM trades WHERE id=?", (trade_id,)
            ).fetchone()
            if row:
                pnl_usdc = row["quantity"] * exit_price - row["amount_usdc"]
                pnl_pct = ((exit_price - row["entry_price"]) / row["entry_price"]) * 100
                conn.execute("""
                    UPDATE trades SET current_price=?, exit_price=?, exit_time=?,
                    exit_time_str=?, status='CLOSED', pnl_usdc=?, pnl_percent=?, close_reason=?
                    WHERE id=?
                """, (exit_price, exit_price, now, now_str, pnl_usdc, pnl_pct, reason, trade_id))
                conn.commit()

    def get_open_trades(self, strategy_id=None):
        conn = self._get_conn()
        if strategy_id:
            rows = conn.execute(
                "SELECT * FROM trades WHERE status='OPEN' AND strategy_id=? ORDER BY entry_time DESC",
                (strategy_id,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM trades WHERE status='OPEN' ORDER BY entry_time DESC").fetchall()
        return [dict(r) for r in rows]

    def get_closed_trades(self, strategy_id=None, limit=100):
        conn = self._get_conn()
        if strategy_id:
            rows = conn.execute(
                "SELECT * FROM trades WHERE status='CLOSED' AND strategy_id=? ORDER BY exit_time DESC LIMIT ?",
                (strategy_id, limit)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM trades WHERE status='CLOSED' ORDER BY exit_time DESC LIMIT ?",
                (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_strategy_stats(self, strategy_id, day_offset=-5):
        conn = self._get_conn()
        open_q = conn.execute("""
            SELECT COUNT(*) as cnt, COALESCE(SUM(amount_usdc),0) as invested,
                   COALESCE(SUM(pnl_usdc),0) as unrealized
            FROM trades WHERE status='OPEN' AND strategy_id=?
        """, (strategy_id,)).fetchone()

        closed_q = conn.execute("""
            SELECT COUNT(*) as cnt, COALESCE(SUM(pnl_usdc),0) as realized,
                   SUM(CASE WHEN pnl_usdc > 0 THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN pnl_usdc <= 0 THEN 1 ELSE 0 END) as losses
            FROM trades WHERE status='CLOSED' AND strategy_id=?
        """, (strategy_id,)).fetchone()

        now = time.time()
        day_start = now - ((now + day_offset * 3600) % 86400) + day_offset * 3600
        today_q = conn.execute("""
            SELECT COALESCE(SUM(pnl_usdc),0) as pnl
            FROM trades WHERE status='CLOSED' AND strategy_id=? AND exit_time >= ?
        """, (strategy_id, day_start)).fetchone()

        total_closed = closed_q["cnt"] or 0
        return {
            "open_count": open_q["cnt"],
            "total_invested": round(open_q["invested"], 2),
            "unrealized_pnl": round(open_q["unrealized"], 4),
            "closed_count": total_closed,
            "realized_pnl": round(closed_q["realized"], 4),
            "wins": closed_q["wins"] or 0,
            "losses": closed_q["losses"] or 0,
            "win_rate": round((closed_q["wins"] or 0) / total_closed * 100, 1) if total_closed > 0 else 0,
            "pnl_today": round(today_q["pnl"], 4)
        }

    def log_signal(self, symbol, volume_ratio, ob_ratio, price):
        conn = self._get_conn()
        with self._lock:
            conn.execute(
                "INSERT INTO signals (symbol, volume_ratio, orderbook_ratio, price, timestamp) VALUES (?,?,?,?,?)",
                (symbol, volume_ratio, ob_ratio, price, time.time()))
            conn.commit()

    def get_trade(self, trade_id):
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
        return dict(row) if row else None
