"""
Read shared Binance cache from /opt/crypto-shared/cache.json
Import this in dashboards/monitors instead of making direct Binance REST calls.
"""
import json
import os
import time

CACHE_FILE = "/opt/crypto-shared/cache.json"
_local = {"data": None, "ts": 0}

def get_shared_cache(max_age=120):
    now = time.time()
    if _local["data"] and now - _local["ts"] < 2:
        return _local["data"]
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE) as f:
                data = json.load(f)
            if now - data.get("ts", 0) < max_age:
                _local["data"] = data
                _local["ts"] = now
                return data
    except Exception:
        pass
    return _local["data"]

def get_eur_rate(fallback=1.08):
    d = get_shared_cache()
    if d and d.get("eur_rate", 0) > 0:
        return d["eur_rate"]
    return fallback

def get_balances():
    d = get_shared_cache()
    if d:
        return d.get("balances", {})
    return {}

def get_ticker_prices():
    d = get_shared_cache()
    if d:
        return d.get("ticker_prices", {})
    return {}

def get_top_pairs(count=300):
    """Get top USDT pairs sorted by volume. Returns list of lowercase symbols."""
    d = get_shared_cache(max_age=600)
    if d and d.get("top_pairs"):
        return d["top_pairs"][:count]
    return None
