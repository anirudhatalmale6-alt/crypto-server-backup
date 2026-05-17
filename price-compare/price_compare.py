#!/usr/bin/env python3
"""PriceCompare Web - Multi-exchange crypto price comparison dashboard.
Rebuilt from C# WinForms to Python web app. Now with volume filtering."""

import os
import json
import time
import logging
import threading
from datetime import datetime
from flask import Flask, jsonify, request, session
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PriceCompare")

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
IGNORE_FILE = os.path.join(CONFIG_DIR, "_ignore_list.txt")
PASSWORD = "guidoleb@@11"
PORT = 5070

def load_ignore_list():
    try:
        with open(IGNORE_FILE, "r") as f:
            return [line.strip().upper() for line in f if line.strip()]
    except:
        return ["SOS", "AMP", "UST", "HFT", "BTT"]

EXCHANGES = {
    "Binance": {
        "url": "https://api.binance.com/api/v3/ticker/24hr",
        "trade_url": "https://www.binance.com/it/trade/{coin}_USDT?theme=dark&type=spot",
        "parse": "binance"
    },
    "Bybit": {
        "url": "https://api.bybit.com/v5/market/tickers?category=spot",
        "trade_url": "https://www.bybit.com/en-US/trade/spot/{coin}/USDT",
        "parse": "bybit"
    },
    "Coinbase": {
        "url": "https://api.coinbase.com/v2/exchange-rates?currency=USD",
        "trade_url": "https://www.coinbase.com/advanced-trade/{coin}-USDT",
        "parse": "coinbase"
    },
    "OKX": {
        "url": "https://www.okx.com/api/v5/market/tickers?instType=SPOT",
        "trade_url": "https://www.okx.com/trade-spot/{coin_lower}-usdt",
        "parse": "okx"
    },
    "KuCoin": {
        "url": "https://api.kucoin.com/api/v1/market/allTickers",
        "trade_url": "https://www.kucoin.com/it/trade/{coin}-USDT",
        "parse": "kucoin"
    },
    "Kraken": {
        "url": "https://api.kraken.com/0/public/Ticker",
        "trade_url": "https://trade.kraken.com/markets/kraken/{coin}/USDT",
        "parse": "kraken"
    },
    "Bitfinex": {
        "url": "https://api-pub.bitfinex.com/v2/tickers?symbols=ALL",
        "trade_url": "https://trading.bitfinex.com/t/{coin}:UST",
        "parse": "bitfinex"
    },
    "Crypto.com": {
        "url": "https://api.crypto.com/exchange/v1/public/get-tickers",
        "trade_url": "https://crypto.com/exchange/trade/{coin}_USDT",
        "parse": "cryptocom"
    },
    "HTX": {
        "url": "https://api.huobi.pro/market/tickers",
        "trade_url": "https://www.htx.com/trade/{coin_lower}_usdt",
        "parse": "htx"
    },
    "Gate.io": {
        "url": "https://api.gateio.ws/api/v4/spot/tickers",
        "trade_url": "https://www.gate.io/trade/{coin}_USDT",
        "parse": "gateio"
    },
    "Bitget": {
        "url": "https://api.bitget.com/api/v2/spot/market/tickers",
        "trade_url": "https://www.bitget.com/it/spot/{coin}USDT_SPBL?type=spot",
        "parse": "bitget"
    },
    "MEXC": {
        "url": "https://api.mexc.com/api/v3/ticker/24hr",
        "trade_url": "https://www.mexc.com/exchange/{coin}_USDT",
        "parse": "mexc"
    },
    "HitBTC": {
        "url": "https://api.hitbtc.com/api/3/public/ticker",
        "trade_url": "https://hitbtc.com/{coin_lower}-to-usdt",
        "parse": "hitbtc"
    },
    "BitMEX": {
        "url": "https://www.bitmex.com/api/v1/instrument/active",
        "trade_url": "https://www.bitmex.com/app/trade/{pair}",
        "parse": "bitmex"
    },
}


def fetch_exchange(name, config):
    """Returns (name, {coin: {"price": float, "vol_usd": float}})"""
    coins = {}
    try:
        resp = requests.get(config["url"], timeout=10,
                          headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            logger.warning(f"{name}: HTTP {resp.status_code}")
            return name, coins
        data = resp.json()
        parser = config["parse"]

        if parser == "binance":
            for item in data:
                pair = item["symbol"]
                if pair.endswith("USDT"):
                    coin = pair[:-4]
                    price = float(item["lastPrice"])
                    vol = float(item.get("quoteVolume", 0))
                    if price > 0:
                        coins[coin] = {"price": price, "vol_usd": vol}

        elif parser == "bybit":
            for item in data.get("result", {}).get("list", []):
                pair = item.get("symbol", "")
                if pair.endswith("USDT"):
                    coin = pair[:-4]
                    price = float(item.get("lastPrice", 0))
                    vol = float(item.get("turnover24h", 0))
                    if price > 0:
                        coins[coin] = {"price": price, "vol_usd": vol}

        elif parser == "coinbase":
            rates = data.get("data", {}).get("rates", {})
            for coin_key, rate in rates.items():
                r = float(rate)
                if r > 0:
                    coins[coin_key.upper()] = {"price": 1.0 / r, "vol_usd": 0}

        elif parser == "okx":
            for item in data.get("data", []):
                pair = item.get("instId", "")
                if pair.endswith("-USDT"):
                    coin = pair.replace("-USDT", "")
                    price = float(item.get("last", 0))
                    vol = float(item.get("volCcy24h", 0))
                    if price > 0:
                        coins[coin] = {"price": price, "vol_usd": vol}

        elif parser == "kucoin":
            for item in data.get("data", {}).get("ticker", []):
                pair = item.get("symbol", "")
                if pair.endswith("-USDT"):
                    coin = pair.replace("-USDT", "")
                    price = float(item.get("last", 0))
                    vol = float(item.get("volValue", 0))
                    if price > 0:
                        coins[coin] = {"price": price, "vol_usd": vol}

        elif parser == "kraken":
            result = data.get("result", {})
            for pair, info in result.items():
                if pair.endswith("USDT"):
                    coin = pair[:-4]
                    if coin == "XBT":
                        coin = "BTC"
                    price = float(info["c"][0])
                    vol_base = float(info["v"][1])
                    if price > 0 and coin not in coins:
                        coins[coin] = {"price": price, "vol_usd": vol_base * price}

        elif parser == "bitfinex":
            for item in data:
                if not isinstance(item, list) or len(item) < 11:
                    continue
                pair = item[0]
                if not pair.startswith("t"):
                    continue
                sym = pair[1:]
                if sym.endswith(":UST"):
                    coin = sym[:-4]
                elif sym.endswith("UST"):
                    coin = sym[:-3]
                else:
                    continue
                if coin == "LUNA":
                    coin = "LUNC"
                elif coin == "LUNA2":
                    coin = "LUNA"
                price = float(item[7])
                vol_base = float(item[8]) if len(item) > 8 else 0
                if price > 0 and coin not in coins:
                    coins[coin] = {"price": price, "vol_usd": abs(vol_base) * price}

        elif parser == "cryptocom":
            for item in data.get("result", {}).get("data", []):
                pair = item.get("i", "")
                if pair.endswith("_USDT"):
                    coin = pair.replace("_USDT", "")
                    price = float(item.get("a", 0))
                    vol = float(item.get("vv", 0))
                    if price > 0:
                        coins[coin] = {"price": price, "vol_usd": vol}

        elif parser == "htx":
            for item in data.get("data", []):
                pair = item.get("symbol", "")
                if pair.endswith("usdt"):
                    coin = pair[:-4].upper()
                    price = float(item.get("close", 0))
                    vol = float(item.get("vol", 0))
                    if price > 0 and coin not in coins:
                        coins[coin] = {"price": price, "vol_usd": vol}

        elif parser == "gateio":
            for item in data:
                pair = item.get("currency_pair", "")
                if pair.endswith("_USDT"):
                    coin = pair.replace("_USDT", "")
                    price = float(item.get("last", 0))
                    vol = float(item.get("quote_volume", 0))
                    if price > 0:
                        coins[coin] = {"price": price, "vol_usd": vol}

        elif parser == "bitget":
            items = data.get("data", [])
            for item in items:
                pair = item.get("symbol", "")
                if pair.endswith("USDT"):
                    coin = pair[:-4]
                    price = float(item.get("lastPr", item.get("close", 0)))
                    vol = float(item.get("quoteVolume", item.get("usdtVolume", 0)))
                    if price > 0 and coin not in coins:
                        coins[coin] = {"price": price, "vol_usd": vol}

        elif parser == "mexc":
            for item in data:
                pair = item.get("symbol", "")
                if pair.endswith("USDT"):
                    coin = pair[:-4]
                    price = float(item.get("lastPrice", 0))
                    vol = float(item.get("quoteVolume", 0))
                    if price > 0:
                        coins[coin] = {"price": price, "vol_usd": vol}

        elif parser == "hitbtc":
            for pair, info in data.items():
                if pair.endswith("USDT"):
                    coin = pair[:-4]
                    price = float(info.get("last") or 0)
                    vol = float(info.get("volume_quote") or 0)
                    if price > 0 and coin not in coins:
                        coins[coin] = {"price": price, "vol_usd": vol}

        elif parser == "bitmex":
            for item in data:
                pair = item.get("symbol", "")
                if pair.endswith("USDT") or pair.endswith("USD"):
                    if pair.endswith("USDT"):
                        coin = pair[:-4]
                    else:
                        coin = pair[:-3]
                    if coin == "XBT":
                        coin = "BTC"
                    price = item.get("lastPrice")
                    vol = float(item.get("foreignNotional24h") or 0)
                    if price and float(price) > 0 and coin not in coins:
                        coins[coin] = {"price": float(price), "vol_usd": vol}

        logger.info(f"{name}: {len(coins)} coins loaded")
    except Exception as e:
        logger.error(f"{name}: {e}")
    return name, coins


class PriceCompareEngine:
    def __init__(self):
        self.market_data = {}
        self.last_update = None
        self.ignore_list = load_ignore_list()
        self.lock = threading.Lock()
        self.update_count = 0

    def refresh(self):
        new_data = {}
        with ThreadPoolExecutor(max_workers=14) as pool:
            futures = {pool.submit(fetch_exchange, name, cfg): name
                      for name, cfg in EXCHANGES.items()}
            for f in as_completed(futures):
                name, coins = f.result()
                if coins:
                    new_data[name] = coins
        with self.lock:
            self.market_data = new_data
            self.last_update = datetime.now().strftime("%H:%M:%S")
            self.update_count += 1
        return len(new_data)

    def get_spreads(self, market1=None, market2=None, min_delta=0,
                    max_delta=50, min_volume=10000):
        with self.lock:
            data = dict(self.market_data)
        ignore = set(self.ignore_list)
        spreads = []

        markets = list(data.keys())
        pairs_done = set()

        for m1 in markets:
            if market1 and m1 != market1:
                continue
            for m2 in markets:
                if market2 and m2 != market2:
                    continue
                if m1 == m2:
                    continue
                pair_key = tuple(sorted([m1, m2]))
                if pair_key in pairs_done:
                    continue
                pairs_done.add(pair_key)

                coins1 = data[m1]
                coins2 = data[m2]
                common = set(coins1.keys()) & set(coins2.keys()) - ignore

                for coin in common:
                    d1 = coins1[coin]
                    d2 = coins2[coin]
                    p1 = d1["price"]
                    p2 = d2["price"]
                    v1 = d1["vol_usd"]
                    v2 = d2["vol_usd"]
                    if p1 <= 0 or p2 <= 0:
                        continue
                    both_have_vol = (v1 > 0 or m1 == "Coinbase") and (v2 > 0 or m2 == "Coinbase")
                    if not both_have_vol:
                        continue
                    min_vol = min(v1, v2) if v1 > 0 and v2 > 0 else max(v1, v2)
                    if min_vol < min_volume:
                        continue
                    if p1 >= p2:
                        high_market, low_market = m1, m2
                        high_price, low_price = p1, p2
                        high_vol, low_vol = v1, v2
                    else:
                        high_market, low_market = m2, m1
                        high_price, low_price = p2, p1
                        high_vol, low_vol = v2, v1
                    ratio = high_price / low_price
                    delta = (ratio - 1) * 100
                    if delta < min_delta or delta > max_delta:
                        continue

                    high_cfg = EXCHANGES[high_market]
                    low_cfg = EXCHANGES[low_market]
                    high_url = high_cfg["trade_url"].format(
                        coin=coin, coin_lower=coin.lower(),
                        pair=coin+"USDT")
                    low_url = low_cfg["trade_url"].format(
                        coin=coin, coin_lower=coin.lower(),
                        pair=coin+"USDT")

                    spreads.append({
                        "coin": coin,
                        "high_market": high_market,
                        "high_price": high_price,
                        "high_url": high_url,
                        "high_vol": round(high_vol),
                        "low_market": low_market,
                        "low_price": low_price,
                        "low_url": low_url,
                        "low_vol": round(low_vol),
                        "delta": round(delta, 4),
                        "net_delta": round(delta - 0.2, 4),
                        "min_vol": round(min_vol),
                    })

        spreads.sort(key=lambda x: x["delta"], reverse=True)
        return spreads

    def get_status(self):
        with self.lock:
            return {
                "exchanges": len(self.market_data),
                "exchange_names": list(self.market_data.keys()),
                "coins_per_exchange": {k: len(v) for k, v in self.market_data.items()},
                "last_update": self.last_update,
                "update_count": self.update_count,
                "ignore_list": self.ignore_list,
            }


engine = PriceCompareEngine()


def create_app():
    app = Flask(__name__)
    app.secret_key = os.urandom(24)

    @app.route("/")
    def index():
        if not session.get("authenticated"):
            return LOGIN_HTML
        return DASHBOARD_HTML

    @app.route("/login", methods=["POST"])
    def login():
        pw = request.form.get("password", "")
        if pw == PASSWORD:
            session["authenticated"] = True
            return '<script>location="/"</script>'
        return '<script>alert("Wrong password");location="/"</script>'

    @app.route("/api/data")
    def api_data():
        if not session.get("authenticated"):
            return jsonify({"error": "unauthorized"}), 401
        m1 = request.args.get("m1")
        m2 = request.args.get("m2")
        min_d = float(request.args.get("min", 0))
        max_d = float(request.args.get("max", 50))
        min_v = float(request.args.get("minvol", 10000))
        if m1 == "any":
            m1 = None
        if m2 == "any":
            m2 = None
        spreads = engine.get_spreads(m1, m2, min_d, max_d, min_v)
        status = engine.get_status()
        return jsonify({"spreads": spreads[:500], "status": status})

    @app.route("/api/refresh", methods=["POST"])
    def api_refresh():
        if not session.get("authenticated"):
            return jsonify({"error": "unauthorized"}), 401
        n = engine.refresh()
        return jsonify({"ok": True, "exchanges": n})

    return app


LOGIN_HTML = '''<!DOCTYPE html>
<html><head><title>PriceCompare</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{background:#0a0a1a;color:#e0e0e0;font-family:Consolas,monospace;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}
.box{background:#12122a;padding:40px;border-radius:12px;border:1px solid #333;text-align:center}
input{background:#1a1a3e;color:#fff;border:1px solid #444;padding:12px 20px;border-radius:6px;font-size:16px;width:220px;font-family:Consolas,monospace}
button{background:#2563eb;color:#fff;border:none;padding:12px 30px;border-radius:6px;cursor:pointer;font-size:16px;margin-top:12px;font-family:Consolas,monospace}
button:hover{background:#1d4ed8}
h2{color:#60a5fa;margin-bottom:24px}
</style></head>
<body><div class="box">
<h2>PriceCompare</h2>
<form method="POST" action="/login">
<input type="password" name="password" placeholder="Password" autofocus><br>
<button type="submit">Login</button>
</form></div></body></html>'''


DASHBOARD_HTML = '''<!DOCTYPE html>
<html><head><title>PriceCompare</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a1a;color:#e0e0e0;font-family:Consolas,monospace;font-size:13px}
.header{background:#12122a;padding:8px 16px;border-bottom:1px solid #333;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.header select,.header input{background:#1a1a3e;color:#fff;border:1px solid #444;padding:5px 8px;border-radius:4px;font-family:Consolas,monospace;font-size:11px}
.header label{color:#888;font-size:10px;white-space:nowrap}
.header button{background:#2563eb;color:#fff;border:none;padding:5px 14px;border-radius:4px;cursor:pointer;font-family:Consolas,monospace;font-size:11px}
.header button:hover{background:#1d4ed8}
.header button.stop{background:#dc2626}
.status{color:#888;font-size:10px}
.swap{cursor:pointer;font-size:16px;color:#60a5fa;padding:0 2px}
.swap:hover{color:#93c5fd}
.sep{color:#333}
table{width:100%;border-collapse:collapse}
th{background:#12122a;color:#888;padding:7px 10px;text-align:left;font-weight:600;font-size:10px;text-transform:uppercase;position:sticky;top:0;border-bottom:1px solid #333;z-index:1}
td{padding:5px 10px;border-bottom:1px solid #1a1a2e;font-size:12px}
tr:hover{background:#1a1a2e}
a{color:#60a5fa;text-decoration:none}
a:hover{text-decoration:underline}
.delta{font-weight:700;font-size:13px}
.profit{color:#4ade80}
.loss{color:#f87171}
.neutral{color:#fbbf24}
.coin{font-weight:700;color:#fff;font-size:13px}
.price{color:#ccc;font-size:11px}
.vol{color:#666;font-size:10px}
.arrow{color:#4ade80;font-weight:700;padding:0 6px}
#container{overflow-y:auto;height:calc(100vh - 46px)}
.summary{padding:6px 16px;background:#0f0f24;border-bottom:1px solid #222;display:flex;gap:16px;font-size:10px;color:#888;flex-wrap:wrap}
.summary span{color:#60a5fa}
.tag{background:#1a3a1a;color:#4ade80;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:600}
.tag.warn{background:#3a3a1a;color:#fbbf24}
</style></head>
<body>
<div class="header">
    <select id="m1" onchange="refresh()"><option value="any">Any Exchange</option></select>
    <span class="swap" onclick="swapMarkets()" title="Swap">&#8644;</span>
    <select id="m2" onchange="refresh()"><option value="any">Any Exchange</option></select>
    <span class="sep">|</span>
    <label>Min%</label><input type="number" id="minDelta" value="0.2" step="0.1" min="0" style="width:55px" onchange="refresh()">
    <label>Max%</label><input type="number" id="maxDelta" value="50" step="1" min="1" style="width:55px" onchange="refresh()">
    <label>MinVol$</label><input type="number" id="minVol" value="10000" step="1000" min="0" style="width:75px" onchange="refresh()">
    <span class="sep">|</span>
    <button onclick="doRefreshPrices()" id="btnRefresh">Refresh</button>
    <button onclick="startAuto()" id="btnStart">Auto 10s</button>
    <button onclick="stopAuto()" id="btnStop" class="stop" style="display:none">Stop</button>
    <span class="status" id="status">Loading...</span>
</div>
<div class="summary" id="summaryBar"><span>Loading...</span></div>
<div id="container">
    <table>
        <thead><tr>
            <th>#</th>
            <th>Coin</th>
            <th>Sell Here (High)</th>
            <th>24h Vol</th>
            <th></th>
            <th>Buy Here (Low)</th>
            <th>24h Vol</th>
            <th>Spread</th>
            <th>Net Profit</th>
        </tr></thead>
        <tbody id="tbody"></tbody>
    </table>
</div>
<script>
var autoTimer = null;
var exchanges = [];

function fmVol(v) {
    if(v >= 1e9) return (v/1e9).toFixed(1)+'B';
    if(v >= 1e6) return (v/1e6).toFixed(1)+'M';
    if(v >= 1e3) return (v/1e3).toFixed(0)+'K';
    return v.toFixed(0);
}

function populateSelects(names) {
    if(exchanges.length === names.length) return;
    exchanges = names;
    ['m1','m2'].forEach(function(id){
        var s = document.getElementById(id);
        var v = s.value;
        s.innerHTML = '<option value="any">Any Exchange</option>';
        names.forEach(function(n){ s.innerHTML += '<option value="'+n+'">'+n+'</option>'; });
        s.value = v;
    });
}

function swapMarkets() {
    var s1=document.getElementById('m1'), s2=document.getElementById('m2');
    var t=s1.value; s1.value=s2.value; s2.value=t;
    refresh();
}

function formatPrice(p) {
    if(p>=1000) return p.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
    if(p>=1) return p.toLocaleString('en-US',{minimumFractionDigits:4,maximumFractionDigits:4});
    if(p>=0.01) return p.toLocaleString('en-US',{minimumFractionDigits:6,maximumFractionDigits:6});
    return p.toLocaleString('en-US',{minimumFractionDigits:8,maximumFractionDigits:8});
}

function refresh() {
    var m1=document.getElementById('m1').value;
    var m2=document.getElementById('m2').value;
    var minD=document.getElementById('minDelta').value||0;
    var maxD=document.getElementById('maxDelta').value||50;
    var minV=document.getElementById('minVol').value||10000;
    fetch('/api/data?m1='+m1+'&m2='+m2+'&min='+minD+'&max='+maxD+'&minvol='+minV)
    .then(function(r){return r.json();})
    .then(function(d){
        if(d.error){location.reload();return;}
        var s=d.status;
        populateSelects(s.exchange_names.sort());
        document.getElementById('status').textContent = s.exchanges+' exch | '+s.last_update+' | #'+s.update_count;
        var profitable = d.spreads.filter(function(x){return x.net_delta>0;}).length;
        document.getElementById('summaryBar').innerHTML =
            '<span>'+d.spreads.length+' spreads</span>' +
            ' <span class="tag">'+profitable+' profitable</span>' +
            ' <span class="tag warn">'+(d.spreads.length-profitable)+' below fees</span>';

        var tb=document.getElementById('tbody');
        var html='';
        d.spreads.forEach(function(s,i){
            var cls = s.net_delta>0 ? 'profit' : (s.net_delta>-0.05 ? 'neutral' : 'loss');
            var volCls1 = s.high_vol>100000?'profit':(s.high_vol>10000?'neutral':'loss');
            var volCls2 = s.low_vol>100000?'profit':(s.low_vol>10000?'neutral':'loss');
            html += '<tr>' +
                '<td style="color:#555">'+(i+1)+'</td>' +
                '<td class="coin"><a href="https://www.tradingview.com/chart/?symbol=BINANCE:'+s.coin+'USDT" target="_blank" style="color:#58a6ff;text-decoration:underline;">'+s.coin+'</a></td>' +
                '<td><a href="'+s.high_url+'" target="_blank">'+s.high_market+'</a> <span class="price">'+formatPrice(s.high_price)+'</span></td>' +
                '<td class="vol '+volCls1+'">$'+fmVol(s.high_vol)+'</td>' +
                '<td class="arrow">&larr;</td>' +
                '<td><a href="'+s.low_url+'" target="_blank">'+s.low_market+'</a> <span class="price">'+formatPrice(s.low_price)+'</span></td>' +
                '<td class="vol '+volCls2+'">$'+fmVol(s.low_vol)+'</td>' +
                '<td class="delta '+cls+'">'+s.delta.toFixed(2)+'%</td>' +
                '<td class="delta '+cls+'">'+s.net_delta.toFixed(2)+'%</td>' +
                '</tr>';
        });
        if(!html) html='<tr><td colspan="9" style="text-align:center;padding:40px;color:#555">No spreads found. Try lowering Min% or MinVol$</td></tr>';
        tb.innerHTML=html;
    });
}

function doRefreshPrices() {
    var btn=document.getElementById('btnRefresh');
    btn.textContent='...'; btn.disabled=true;
    fetch('/api/refresh',{method:'POST'})
    .then(function(r){return r.json();})
    .then(function(){btn.textContent='Refresh';btn.disabled=false;refresh();});
}

function startAuto() {
    if(autoTimer) clearInterval(autoTimer);
    doRefreshPrices();
    autoTimer=setInterval(doRefreshPrices,10000);
    document.getElementById('btnStart').style.display='none';
    document.getElementById('btnStop').style.display='';
}
function stopAuto() {
    if(autoTimer){clearInterval(autoTimer);autoTimer=null;}
    document.getElementById('btnStart').style.display='';
    document.getElementById('btnStop').style.display='none';
}

doRefreshPrices();
</script>
</body></html>'''


if __name__ == "__main__":
    logger.info("Initial price fetch...")
    n = engine.refresh()
    logger.info(f"Loaded {n} exchanges")
    app = create_app()
    app.run(host="0.0.0.0", port=PORT, debug=False)
