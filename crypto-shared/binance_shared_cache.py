#!/usr/bin/env python3
"""
Shared Binance data fetcher.
Runs as a service, fetches common data from Binance every 30 seconds,
writes to /opt/crypto-shared/cache.json for all dashboards to read.

Data fetched:
- Account balances (all assets)
- EUR/USDT rate
- All ticker prices (for total portfolio)
- Top 300 USDT pairs by volume (for monitor startup)
"""
import json
import time
import hmac
import hashlib
import logging
import os
import requests
from urllib.parse import urlencode

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/opt/crypto-shared/shared_cache.log")
    ]
)
logger = logging.getLogger("shared-cache")

CACHE_FILE = "/opt/crypto-shared/cache.json"
REST_URL = "https://api.binance.com"
CONFIG_FILE = "/opt/crypto-paper-7081/config.json"

def load_keys():
    with open(CONFIG_FILE) as f:
        cfg = json.load(f)
    b = cfg.get("trading", {})
    return b.get("binance_api_key", ""), b.get("binance_api_secret", "")

def sign_params(params, secret):
    params["timestamp"] = int(time.time() * 1000)
    query = urlencode(params)
    sig = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    params["signature"] = sig
    return params

def load_existing():
    """Load existing cache to preserve data during rate limits."""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return None

def fetch_and_write():
    api_key, api_secret = load_keys()
    old = load_existing()
    data = {
        "ts": time.time(),
        "eur_rate": old.get("eur_rate", 0) if old else 0,
        "balances": old.get("balances", {}) if old else {},
        "ticker_prices": old.get("ticker_prices", {}) if old else {},
        "top_pairs": old.get("top_pairs", []) if old else [],
        "top_pairs_ts": old.get("top_pairs_ts", 0) if old else 0,
        "error": None
    }

    rate_limited = False

    # EUR rate
    try:
        r = requests.get(f"{REST_URL}/api/v3/ticker/price",
                         params={"symbol": "EURUSDT"}, timeout=5)
        if r.status_code == 200:
            data["eur_rate"] = float(r.json()["price"])
        elif r.status_code == 418:
            rate_limited = True
    except Exception as e:
        logger.error(f"EUR rate fetch: {e}")

    if rate_limited:
        logger.warning("Rate limited (418), keeping old cache")
        return False

    # Account balances
    try:
        if api_key and api_secret:
            params = sign_params({}, api_secret)
            r = requests.get(f"{REST_URL}/api/v3/account",
                             params=params,
                             headers={"X-MBX-APIKEY": api_key},
                             timeout=5)
            if r.status_code == 200:
                new_bals = {}
                for b in r.json().get("balances", []):
                    total = float(b["free"]) + float(b["locked"])
                    if total > 0:
                        new_bals[b["asset"]] = total
                data["balances"] = new_bals
            elif r.status_code == 418:
                return False
    except Exception as e:
        logger.error(f"Balance fetch: {e}")

    # All ticker prices
    try:
        r = requests.get(f"{REST_URL}/api/v3/ticker/price", timeout=5)
        if r.status_code == 200:
            data["ticker_prices"] = {p["symbol"]: float(p["price"]) for p in r.json()}
        elif r.status_code == 418:
            return False
    except Exception as e:
        logger.error(f"Ticker prices fetch: {e}")

    # Top 300 pairs (refresh every 5 minutes - heavy endpoint)
    if time.time() - data["top_pairs_ts"] > 300:
        try:
            r = requests.get(f"{REST_URL}/api/v3/ticker/24hr", timeout=30)
            if r.status_code == 200:
                tickers = r.json()
                usdt_pairs = [
                    t for t in tickers
                    if t["symbol"].endswith("USDT")
                    and float(t["quoteVolume"]) > 0
                ]
                usdt_pairs.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)
                data["top_pairs"] = [t["symbol"].lower() for t in usdt_pairs[:300]]
                data["top_pairs_ts"] = time.time()
                logger.info(f"Top pairs updated: {len(data['top_pairs'])} pairs")
            elif r.status_code == 418:
                return False
        except Exception as e:
            logger.error(f"Top pairs fetch: {e}")

    # Write atomically
    tmp = CACHE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, CACHE_FILE)
    logger.info(f"Cache updated: EUR={data['eur_rate']:.4f}, "
                f"{len(data['balances'])} assets, "
                f"{len(data['ticker_prices'])} tickers, "
                f"{len(data['top_pairs'])} pairs")
    return True

def main():
    logger.info("Shared Binance cache service started")
    backoff = 0
    while True:
        now = time.time()
        if now < backoff:
            time.sleep(10)
            continue
        ok = fetch_and_write()
        if not ok:
            backoff = time.time() + 120
            logger.warning("Backing off 2 minutes")
        time.sleep(30)

if __name__ == "__main__":
    main()
