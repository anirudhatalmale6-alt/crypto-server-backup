"""
Multi-Strategy Control Panel - Port 1111
Comparison table like port 9999, plus settings/control for each port.
Click a port to open its settings modal with enable/disable, config editing, and trade management.
"""
from flask import Flask, jsonify, request, Response
import sqlite3
import os
import json
import requests as req
from functools import wraps
from datetime import datetime

app = Flask(__name__)

PASSWORD = "guidoleb@@11"
DEFAULT_START = "2026-05-07 05:00:00"
DAY_START_HOUR = 5

PORTS = [7081, 8090, 8091, 8092, 8093, 8094, 8095, 8096, 8097, 8098, 8099, 9000, 9001, 9002, 9010, 9011, 9012]

def check_auth(username, pw):
    return username == "admin" and pw == PASSWORD

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return Response("Auth required", 401, {"WWW-Authenticate": 'Basic realm="Login"'})
        return f(*args, **kwargs)
    return decorated

def get_db_path(port):
    return f"/opt/crypto-paper-{port}/paper_{port}.db"

def get_config(port):
    try:
        with open(f"/opt/crypto-paper-{port}/config.json") as f:
            return json.load(f)
    except Exception:
        return {}

def save_config(port, cfg):
    path = f"/opt/crypto-paper-{port}/config.json"
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)

def query_port(port, start_date=None):
    db = get_db_path(port)
    if not os.path.exists(db):
        return None
    try:
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        cfg = get_config(port)
        amount = cfg.get("trading", {}).get("amount_per_trade_eur", 0)
        mode = cfg.get("trading", {}).get("mode", "demo")
        window = cfg.get("detection", {}).get("pump_window_seconds", 0)

        date_filter = ""
        params = []
        if start_date:
            date_filter = " AND exit_time_str >= ?"
            params = [start_date]

        row = conn.execute("""
            SELECT COUNT(*) as total_closed,
                COALESCE(SUM(pnl_eur), 0) as total_pnl,
                COALESCE(SUM(CASE WHEN pnl_eur > 0 THEN 1 ELSE 0 END), 0) as wins,
                COALESCE(SUM(CASE WHEN pnl_eur <= 0 THEN 1 ELSE 0 END), 0) as losses
            FROM trades WHERE status='CLOSED'""" + date_filter, params).fetchone()

        total_closed = row["total_closed"]
        total_pnl = round(row["total_pnl"], 2)
        wins = row["wins"]
        win_rate = round(wins / total_closed * 100, 1) if total_closed > 0 else 0
        open_count = conn.execute("SELECT COUNT(*) as c FROM trades WHERE status='OPEN'").fetchone()["c"]

        days = conn.execute("""
            SELECT DATE(exit_time_str, '-5 hours') as day,
                COUNT(*) as trades,
                ROUND(SUM(pnl_eur), 2) as pnl,
                SUM(CASE WHEN pnl_eur > 0 THEN 1 ELSE 0 END) as w,
                SUM(CASE WHEN pnl_eur <= 0 THEN 1 ELSE 0 END) as l
            FROM trades WHERE status='CLOSED' AND exit_time_str IS NOT NULL""" + date_filter + """
            GROUP BY DATE(exit_time_str, '-5 hours') ORDER BY day
        """, params).fetchall()

        day_max_sim = {}
        try:
            sim_q = """SELECT DATE(t1.entry_time_str, '-5 hours') as day,
                MAX((SELECT COUNT(*) FROM trades t2
                    WHERE t2.entry_time <= t1.entry_time
                    AND (t2.exit_time IS NULL OR t2.exit_time > t1.entry_time)
                )) as mx
                FROM trades t1 WHERE t1.id % 5 = 0"""
            sim_p = []
            if start_date:
                sim_q += " AND t1.entry_time_str >= ?"
                sim_p = [start_date]
            sim_q += " GROUP BY DATE(t1.entry_time_str, '-5 hours')"
            for r in conn.execute(sim_q, sim_p).fetchall():
                day_max_sim[r["day"]] = r["mx"] or 0
        except Exception:
            pass

        daily = {}
        for d in days:
            wr = round(d["w"] / d["trades"] * 100, 1) if d["trades"] > 0 else 0
            ms = day_max_sim.get(d["day"], 0)
            mc = ms * amount
            daily[d["day"]] = {"pnl": d["pnl"], "trades": d["trades"], "wins": d["w"], "losses": d["l"], "win_rate": wr, "max_sim": ms, "max_capital": round(mc, 0)}

        sim_filter = " AND entry_time_str >= ?" if start_date else ""
        sim_params = [start_date] if start_date else []
        max_sim = conn.execute("""
            SELECT MAX(oc) as mx FROM (
                SELECT (SELECT COUNT(*) FROM trades t2
                    WHERE t2.entry_time <= t1.entry_time
                    AND (t2.exit_time IS NULL OR t2.exit_time > t1.entry_time)
                ) as oc FROM trades t1 WHERE id % 20 = 0""" + sim_filter + ")", sim_params).fetchone()["mx"] or 0
        max_capital = max_sim * amount

        conn.close()
        return {
            "port": port, "mode": mode, "amount": amount, "window": window,
            "total_pnl": total_pnl, "total_closed": total_closed, "open_count": open_count,
            "max_open_history": max(open_count, max_sim), "wins": wins, "losses": row["losses"],
            "win_rate": win_rate, "max_simultaneous": max_sim, "max_capital": round(max_capital, 0),
            "daily": daily
        }
    except Exception as e:
        return {"port": port, "error": str(e)}


@app.route("/")
@requires_auth
def index():
    return HTML


@app.route("/api/data")
@requires_auth
def api_data():
    start = request.args.get("start", DEFAULT_START)
    results = []
    all_days = set()
    for port in PORTS:
        data = query_port(port, start_date=start)
        if data:
            results.append(data)
            if "daily" in data:
                all_days.update(data["daily"].keys())
    return jsonify({"ports": results, "days": sorted(all_days), "start_date": start})


@app.route("/api/port-config/<int:port>")
@requires_auth
def api_port_config(port):
    cfg = get_config(port)
    trading = cfg.get("trading", {})
    detection = cfg.get("detection", {})
    open_trades = []
    db = get_db_path(port)
    if os.path.exists(db):
        try:
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM trades WHERE status='OPEN' ORDER BY entry_time DESC").fetchall()
            for r in rows:
                open_trades.append(dict(r))
            conn.close()
        except Exception:
            pass
    return jsonify({
        "port": port,
        "mode": trading.get("mode", "demo"),
        "amount": trading.get("amount_per_trade_eur", 10),
        "max_trades": trading.get("max_simultaneous_trades", 100),
        "pump_tp": trading.get("pump_tp_percent", 30),
        "pump_sl": trading.get("pump_sl_percent", 10),
        "max_duration": trading.get("max_duration_hours", 2),
        "pump_window": detection.get("pump_window_seconds", 600),
        "volume_spike": detection.get("volume_spike_multiplier", 3.0),
        "ob_buy_ratio": detection.get("orderbook_buy_ratio", 1.5),
        "open_trades": open_trades
    })


@app.route("/api/port-config/<int:port>", methods=["POST"])
@requires_auth
def api_save_port_config(port):
    data = request.get_json()
    cfg = get_config(port)
    if "trading" not in cfg:
        cfg["trading"] = {}
    if "detection" not in cfg:
        cfg["detection"] = {}

    if "mode" in data:
        cfg["trading"]["mode"] = data["mode"]
    if "amount" in data:
        cfg["trading"]["amount_per_trade_eur"] = float(data["amount"])
    if "max_trades" in data:
        cfg["trading"]["max_simultaneous_trades"] = int(data["max_trades"])
    if "pump_tp" in data:
        cfg["trading"]["pump_tp_percent"] = float(data["pump_tp"])
    if "pump_sl" in data:
        cfg["trading"]["pump_sl_percent"] = float(data["pump_sl"])
    if "max_duration" in data:
        cfg["trading"]["max_duration_hours"] = float(data["max_duration"])
    if "pump_window" in data:
        cfg["detection"]["pump_window_seconds"] = int(data["pump_window"])
    if "volume_spike" in data:
        cfg["detection"]["volume_spike_multiplier"] = float(data["volume_spike"])
    if "ob_buy_ratio" in data:
        cfg["detection"]["orderbook_buy_ratio"] = float(data["ob_buy_ratio"])

    save_config(port, cfg)

    # Also push settings to the running port via its API
    try:
        api_data = {}
        if "amount" in data:
            api_data["amount"] = float(data["amount"])
        if "max_trades" in data:
            api_data["max_trades"] = int(data["max_trades"])
        if "pump_tp" in data:
            api_data["pump_tp_percent"] = float(data["pump_tp"])
        if "pump_sl" in data:
            api_data["pump_sl_percent"] = float(data["pump_sl"])
        if "max_duration" in data:
            api_data["max_duration_hours"] = float(data["max_duration"])
        if "pump_window" in data:
            api_data["pump_window_seconds"] = int(data["pump_window"])
        if "volume_spike" in data:
            api_data["volume_spike_multiplier"] = float(data["volume_spike"])
        if "ob_buy_ratio" in data:
            api_data["orderbook_buy_ratio"] = float(data["ob_buy_ratio"])
        if "mode" in data:
            api_data["mode"] = data["mode"]
        if api_data:
            req.post(f"http://127.0.0.1:{port}/api/settings", json=api_data, timeout=5)
    except Exception:
        pass

    return jsonify({"status": "saved", "port": port})


@app.route("/api/port-close-all/<int:port>", methods=["POST"])
@requires_auth
def api_close_all(port):
    try:
        r = req.post(f"http://127.0.0.1:{port}/api/close-all", timeout=10)
        return jsonify(r.json())
    except Exception:
        # Fallback: close directly in DB
        db = get_db_path(port)
        closed = 0
        if os.path.exists(db):
            try:
                conn = sqlite3.connect(db)
                conn.execute("UPDATE trades SET status='CLOSED', exit_time=?, exit_time_str=?, close_reason='CLOSE_ALL_1111' WHERE status='OPEN'",
                    (datetime.utcnow().timestamp(), datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
                closed = conn.total_changes
                conn.commit()
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "ok", "closed": closed, "fallback": True})


@app.route("/api/port-close-trade/<int:port>/<int:trade_id>", methods=["POST"])
@requires_auth
def api_close_trade(port, trade_id):
    try:
        r = req.post(f"http://127.0.0.1:{port}/api/close-position/{trade_id}", timeout=10)
        return jsonify(r.json())
    except Exception:
        db = get_db_path(port)
        if os.path.exists(db):
            try:
                conn = sqlite3.connect(db)
                conn.execute("UPDATE trades SET status='CLOSED', exit_time=?, exit_time_str=?, close_reason='MANUAL_1111' WHERE id=? AND status='OPEN'",
                    (datetime.utcnow().timestamp(), datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), trade_id))
                conn.commit()
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "closed", "fallback": True})


HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Multi-Strategy Control Panel</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0d1117; color: #c9d1d9; font-family: 'Consolas', 'Monaco', monospace; font-size: 12px; }
.header { background: #161b22; padding: 12px 20px; border-bottom: 1px solid #30363d; display: flex; align-items: center; justify-content: space-between; }
.header h1 { font-size: 16px; color: #58a6ff; }
.container { padding: 15px; overflow-x: auto; }
table { border-collapse: collapse; width: 100%; min-width: 800px; }
th { background: #161b22; color: #8b949e; font-size: 11px; text-transform: uppercase; padding: 8px 6px; border: 1px solid #21262d; position: sticky; top: 0; z-index: 10; white-space: nowrap; }
td { padding: 6px; border: 1px solid #21262d; text-align: right; white-space: nowrap; }
td.port { text-align: left; font-weight: 700; color: #58a6ff; background: #161b22; position: sticky; left: 0; z-index: 5; cursor: pointer; }
td.port:hover { text-decoration: underline; }
td.total { font-weight: 700; background: #161b22; }
.pos { color: #3fb950; }
.neg { color: #f85149; }
.zero { color: #8b949e; }
.day-header { background: #1c2333; color: #58a6ff; font-weight: 700; text-align: center; }
.sub-header { background: #161b22; color: #8b949e; font-size: 10px; text-align: center; }
tr:hover td { background: #1c2128; }
tr:hover td.port { background: #1c2128; }
.live { color: #f0883e; font-weight: 700; }
.summary { margin: 15px 0; display: flex; gap: 15px; flex-wrap: wrap; }
.summary-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px 16px; min-width: 150px; }
.summary-card .label { color: #8b949e; font-size: 10px; text-transform: uppercase; }
.summary-card .value { font-size: 18px; font-weight: 700; margin-top: 4px; }
.totals-row td { background: #1c2333 !important; font-weight: 700; border-top: 2px solid #58a6ff; }

/* Modal */
.modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,.7); z-index: 100; justify-content: center; align-items: center; }
.modal-overlay.open { display: flex; }
.modal { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 24px; width: 700px; max-height: 85vh; overflow-y: auto; }
.modal h2 { color: #58a6ff; font-size: 16px; margin-bottom: 16px; border-bottom: 1px solid #30363d; padding-bottom: 8px; }
.modal-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 16px; }
.modal-grid label { font-size: 11px; color: #8b949e; text-transform: uppercase; display: block; margin-bottom: 4px; }
.modal-grid input, .modal-grid select { width: 100%; background: #0d1117; border: 1px solid #30363d; color: #f0f6fc; padding: 8px; border-radius: 4px; font-size: 14px; font-family: inherit; }
.modal-btns { display: flex; gap: 10px; margin-top: 16px; justify-content: flex-end; }
.modal-btns button { padding: 8px 20px; border: none; border-radius: 6px; font-size: 12px; font-weight: 700; cursor: pointer; font-family: inherit; }
.btn-save { background: #238636; color: #fff; }
.btn-save:hover { background: #2ea043; }
.btn-cancel { background: #21262d; color: #c9d1d9; }
.btn-cancel:hover { background: #30363d; }
.btn-close-all { background: #b91c1c; color: #fff; }
.btn-close-all:hover { background: #dc2626; }
.btn-demo { background: #1f6feb; color: #fff; }
.btn-live { background: #f0883e; color: #fff; }

/* Trades table in modal */
.trades-section { margin-top: 16px; }
.trades-section h3 { font-size: 13px; color: #8b949e; margin-bottom: 8px; }
.trades-table { width: 100%; border-collapse: collapse; font-size: 11px; }
.trades-table th { padding: 6px 4px; font-size: 10px; }
.trades-table td { padding: 5px 4px; font-size: 11px; }

#mStatus { margin-top: 8px; font-size: 12px; text-align: center; }
</style>
</head>
<body>
<div class="header">
    <h1>Multi-Strategy Control Panel (Port 1111)</h1>
    <div style="display:flex;align-items:center;gap:12px">
        <label style="color:#8b949e;font-size:11px">From: <input type="datetime-local" id="startDate" value="2026-05-07T05:00" style="background:#0d1117;color:#c9d1d9;border:1px solid #30363d;padding:4px 8px;border-radius:4px;font-family:inherit;font-size:12px"></label>
        <div style="color:#8b949e;font-size:11px" id="status">Loading...</div>
    </div>
</div>
<div class="container">
    <div class="summary" id="summary"></div>
    <div id="tableContainer"></div>
</div>

<!-- Settings Modal -->
<div class="modal-overlay" id="portModal" onclick="if(event.target===this)closeModal()">
<div class="modal">
<div style="display:flex;justify-content:space-between;align-items:center">
    <h2 id="modalTitle" style="margin:0;border:none;padding:0">Port Settings</h2>
    <button onclick="closeModal()" style="background:none;border:none;color:#8b949e;font-size:22px;cursor:pointer">&times;</button>
</div>

<div style="display:flex;gap:10px;margin:12px 0;align-items:center">
    <span style="color:#8b949e;font-size:12px">Mode:</span>
    <span id="mModeLabel" style="font-weight:700;font-size:14px">DEMO</span>
    <button class="btn-demo" id="mToggleMode" onclick="toggleMode()" style="padding:4px 12px;font-size:11px;border:none;border-radius:4px;cursor:pointer">Switch to LIVE</button>
</div>

<div class="modal-grid">
    <div><label>Trade Amount (USDC)</label><input type="number" step="1" id="mAmount"></div>
    <div><label>Max Positions</label><input type="number" step="1" id="mMaxTrades"></div>
    <div><label>Take Profit (%)</label><input type="number" step="0.1" id="mTP"></div>
    <div><label>Stop Loss (%)</label><input type="number" step="0.1" id="mSL"></div>
    <div><label>Max Duration (h)</label><input type="number" step="0.5" id="mDuration"></div>
    <div><label>Pump Window (s)</label><input type="number" step="10" id="mWindow"></div>
    <div><label>Volume Spike (x)</label><input type="number" step="0.1" id="mSpike"></div>
    <div><label>OB Buy Ratio (x)</label><input type="number" step="0.1" id="mOB"></div>
</div>

<div class="modal-btns">
    <button class="btn-close-all" onclick="closeAllTrades()">CLOSE ALL POSITIONS</button>
    <button class="btn-cancel" onclick="closeModal()">CANCEL</button>
    <button class="btn-save" onclick="savePortSettings()">SAVE SETTINGS</button>
</div>

<div id="mStatus"></div>

<div class="trades-section" id="mTradesSection">
    <h3>Open Positions (<span id="mTradeCount">0</span>)</h3>
    <div style="max-height:300px;overflow-y:auto">
        <table class="trades-table">
            <thead><tr><th>Symbol</th><th>Entry Price</th><th>Amount</th><th>Is Live</th><th>Entry Time</th><th>Action</th></tr></thead>
            <tbody id="mTradesBody"><tr><td colspan="6" style="text-align:center;color:#8b949e">Loading...</td></tr></tbody>
        </table>
    </div>
</div>

</div>
</div>

<script>
function pnlClass(v) { return v > 0 ? 'pos' : v < 0 ? 'neg' : 'zero'; }
function fmt(v, d) { return v !== undefined && v !== null ? Number(v).toFixed(d || 2) : '--'; }

var _modalPort = null;
var _modalMode = 'demo';

async function refresh() {
    try {
        var sd = document.getElementById('startDate').value.replace('T', ' ') + ':00';
        var r = await fetch('/api/data?start=' + encodeURIComponent(sd) + '&t=' + Date.now());
        var data = await r.json();
        render(data);
        document.getElementById('status').textContent = 'Updated: ' + new Date().toLocaleTimeString() + ' (30s)';
    } catch(e) {
        document.getElementById('status').textContent = 'Error: ' + e.message;
    }
}

function render(data) {
    var ports = data.ports;
    var days = data.days;

    var totalPnl = ports.reduce(function(s, p) { return s + (p.total_pnl || 0); }, 0);
    var bestPort = ports.reduce(function(best, p) { return (!best || (p.total_pnl || 0) > (best.total_pnl || 0)) ? p : best; }, null);
    var totalTrades = ports.reduce(function(s, p) { return s + (p.total_closed || 0); }, 0);
    var totalCapital = ports.reduce(function(s, p) { return s + (p.max_capital || 0); }, 0);
    var totalOpen = ports.reduce(function(s, p) { return s + (p.open_count || 0); }, 0);
    var livePorts = ports.filter(function(p) { return p.mode === 'live'; }).length;

    var sh = '';
    sh += '<div class="summary-card"><div class="label">Total P&L</div><div class="value ' + pnlClass(totalPnl) + '">' + fmt(totalPnl) + ' USDC</div></div>';
    sh += '<div class="summary-card"><div class="label">Best Port</div><div class="value" style="color:#58a6ff">' + (bestPort ? bestPort.port : '--') + ' (' + fmt(bestPort ? bestPort.total_pnl : 0) + ')</div></div>';
    sh += '<div class="summary-card"><div class="label">Total Trades</div><div class="value">' + totalTrades + '</div></div>';
    sh += '<div class="summary-card"><div class="label">Open Positions</div><div class="value">' + totalOpen + '</div></div>';
    sh += '<div class="summary-card"><div class="label">Live Ports</div><div class="value" style="color:#f0883e">' + livePorts + ' / ' + ports.length + '</div></div>';
    sh += '<div class="summary-card"><div class="label">Active Days</div><div class="value">' + days.length + '</div></div>';
    document.getElementById('summary').innerHTML = sh;

    // Table
    var h = '<table><thead><tr>';
    h += '<th style="position:sticky;left:0;z-index:15;min-width:60px">Port</th>';
    h += '<th>Mode</th>';
    h += '<th>Window</th>';
    h += '<th>Amount</th>';
    h += '<th style="min-width:80px">Total P&L</th>';
    h += '<th>Trades</th>';
    h += '<th>Open</th>';
    h += '<th>Max Sim</th>';
    h += '<th>Max Capital</th>';
    h += '<th>% P&L/Cap</th>';
    h += '<th>Win%</th>';

    days.forEach(function(d) {
        var parts = d.split('-');
        var label = parts[2] + '/' + parts[1];
        h += '<th colspan="3" class="day-header">' + label + '</th>';
    });
    h += '</tr><tr>';
    h += '<th style="position:sticky;left:0;z-index:15"></th>';
    h += '<th></th><th></th><th></th><th></th><th></th><th></th><th></th><th></th><th></th><th></th>';
    days.forEach(function() {
        h += '<th class="sub-header">P&L</th><th class="sub-header">Trades</th><th class="sub-header">Win%</th>';
    });
    h += '</tr></thead><tbody>';

    var dayTotals = {};
    days.forEach(function(d) { dayTotals[d] = { pnl: 0, trades: 0, wins: 0 }; });

    ports.forEach(function(p) {
        if (p.error) return;
        var modeClass = p.mode === 'live' ? ' live' : '';
        var pctCapital = p.max_capital > 0 ? (p.total_pnl / p.max_capital * 100) : 0;
        h += '<tr>';
        h += '<td class="port' + modeClass + '" onclick="openModal(' + p.port + ')">' + p.port + '</td>';
        h += '<td' + (p.mode === 'live' ? ' class="live"' : '') + '>' + (p.mode || 'demo').toUpperCase() + '</td>';
        h += '<td>' + (p.window || '--') + 's</td>';
        h += '<td>' + fmt(p.amount, 0) + '</td>';
        h += '<td class="total ' + pnlClass(p.total_pnl) + '">' + fmt(p.total_pnl) + '</td>';
        h += '<td>' + (p.total_closed || 0) + '</td>';
        h += '<td>' + (p.open_count || 0) + '</td>';
        h += '<td>' + (p.max_simultaneous || '--') + '</td>';
        h += '<td>' + fmt(p.max_capital, 0) + '</td>';
        h += '<td class="' + pnlClass(pctCapital) + '">' + fmt(pctCapital, 1) + '%</td>';
        h += '<td>' + fmt(p.win_rate, 1) + '%</td>';

        days.forEach(function(d) {
            var dd = (p.daily || {})[d];
            if (dd) {
                h += '<td class="' + pnlClass(dd.pnl) + '">' + fmt(dd.pnl) + '</td>';
                h += '<td>' + dd.trades + '</td>';
                h += '<td>' + fmt(dd.win_rate, 0) + '%</td>';
                dayTotals[d].pnl += dd.pnl || 0;
                dayTotals[d].trades += dd.trades || 0;
                dayTotals[d].wins += dd.wins || 0;
            } else {
                h += '<td class="zero">--</td><td class="zero">--</td><td class="zero">--</td>';
            }
        });
        h += '</tr>';
    });

    // Totals row
    h += '<tr class="totals-row">';
    h += '<td class="port" style="color:#f0883e;cursor:default">TOTAL</td>';
    h += '<td></td><td></td><td></td>';
    h += '<td class="' + pnlClass(totalPnl) + '">' + fmt(totalPnl) + '</td>';
    h += '<td>' + totalTrades + '</td>';
    h += '<td>' + totalOpen + '</td>';
    h += '<td></td>';
    h += '<td>' + fmt(totalCapital, 0) + '</td>';
    var totalPct = totalCapital > 0 ? (totalPnl / totalCapital * 100) : 0;
    h += '<td class="' + pnlClass(totalPct) + '">' + fmt(totalPct, 1) + '%</td>';
    h += '<td></td>';
    days.forEach(function(d) {
        var dt = dayTotals[d];
        var wr = dt.trades > 0 ? (dt.wins / dt.trades * 100) : 0;
        h += '<td class="' + pnlClass(dt.pnl) + '">' + fmt(dt.pnl) + '</td>';
        h += '<td>' + dt.trades + '</td>';
        h += '<td>' + fmt(wr, 0) + '%</td>';
    });
    h += '</tr>';
    h += '</tbody></table>';
    document.getElementById('tableContainer').innerHTML = h;
}

function openModal(port) {
    _modalPort = port;
    document.getElementById('modalTitle').textContent = 'Port ' + port + ' - Settings';
    document.getElementById('mStatus').textContent = 'Loading...';
    document.getElementById('mStatus').style.color = '#8b949e';
    document.getElementById('mTradesBody').innerHTML = '<tr><td colspan="6" style="text-align:center;color:#8b949e">Loading...</td></tr>';
    document.getElementById('portModal').classList.add('open');

    fetch('/api/port-config/' + port + '?t=' + Date.now())
        .then(function(r) { return r.json(); })
        .then(function(d) {
            _modalMode = d.mode || 'demo';
            updateModeUI();
            document.getElementById('mAmount').value = d.amount || 10;
            document.getElementById('mMaxTrades').value = d.max_trades || 100;
            document.getElementById('mTP').value = d.pump_tp || 30;
            document.getElementById('mSL').value = d.pump_sl || 10;
            document.getElementById('mDuration').value = d.max_duration || 2;
            document.getElementById('mWindow').value = d.pump_window || 600;
            document.getElementById('mSpike').value = d.volume_spike || 3.0;
            document.getElementById('mOB').value = d.ob_buy_ratio || 1.5;

            var trades = d.open_trades || [];
            document.getElementById('mTradeCount').textContent = trades.length;
            if (trades.length === 0) {
                document.getElementById('mTradesBody').innerHTML = '<tr><td colspan="6" style="text-align:center;color:#8b949e">No open positions</td></tr>';
            } else {
                var th = '';
                trades.forEach(function(t) {
                    th += '<tr>';
                    th += '<td>' + (t.symbol || '') + '</td>';
                    th += '<td>' + parseFloat(t.entry_price || 0).toFixed(8) + '</td>';
                    th += '<td>' + fmt(t.amount_eur || t.amount_usdc || 0) + '</td>';
                    th += '<td>' + (t.is_live ? '<span style="color:#f0883e">LIVE</span>' : 'DEMO') + '</td>';
                    th += '<td>' + (t.entry_time_str || '') + '</td>';
                    th += '<td><button onclick="closeSingleTrade(' + t.id + ')" style="background:#da3633;color:#fff;border:none;padding:3px 8px;border-radius:4px;cursor:pointer;font-size:10px">Close</button></td>';
                    th += '</tr>';
                });
                document.getElementById('mTradesBody').innerHTML = th;
            }
            document.getElementById('mStatus').textContent = '';
        })
        .catch(function(e) {
            document.getElementById('mStatus').textContent = 'Error loading: ' + e.message;
            document.getElementById('mStatus').style.color = '#f85149';
        });
}

function updateModeUI() {
    var label = document.getElementById('mModeLabel');
    var btn = document.getElementById('mToggleMode');
    if (_modalMode === 'live') {
        label.textContent = 'LIVE';
        label.style.color = '#f0883e';
        btn.textContent = 'Switch to DEMO';
        btn.className = 'btn-demo';
    } else {
        label.textContent = 'DEMO';
        label.style.color = '#3fb950';
        btn.textContent = 'Switch to LIVE';
        btn.className = 'btn-live';
    }
}

function toggleMode() {
    if (_modalMode === 'live') {
        _modalMode = 'demo';
    } else {
        if (!confirm('Switch port ' + _modalPort + ' to LIVE mode? Real money will be used!')) return;
        _modalMode = 'live';
    }
    updateModeUI();
}

function closeModal() {
    document.getElementById('portModal').classList.remove('open');
    _modalPort = null;
}

function savePortSettings() {
    if (!_modalPort) return;
    document.getElementById('mStatus').textContent = 'Saving...';
    document.getElementById('mStatus').style.color = '#f0883e';

    var data = {
        mode: _modalMode,
        amount: parseFloat(document.getElementById('mAmount').value),
        max_trades: parseInt(document.getElementById('mMaxTrades').value),
        pump_tp: parseFloat(document.getElementById('mTP').value),
        pump_sl: parseFloat(document.getElementById('mSL').value),
        max_duration: parseFloat(document.getElementById('mDuration').value),
        pump_window: parseInt(document.getElementById('mWindow').value),
        volume_spike: parseFloat(document.getElementById('mSpike').value),
        ob_buy_ratio: parseFloat(document.getElementById('mOB').value)
    };

    fetch('/api/port-config/' + _modalPort, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    }).then(function(r) { return r.json(); })
    .then(function(d) {
        document.getElementById('mStatus').textContent = 'Settings saved! (config.json updated + pushed to running port)';
        document.getElementById('mStatus').style.color = '#3fb950';
        setTimeout(function() { refresh(); }, 1000);
    })
    .catch(function(e) {
        document.getElementById('mStatus').textContent = 'Error: ' + e.message;
        document.getElementById('mStatus').style.color = '#f85149';
    });
}

function closeAllTrades() {
    if (!_modalPort) return;
    if (!confirm('Close ALL positions on port ' + _modalPort + '?')) return;
    if (!confirm('FINAL CONFIRMATION: Close ALL positions on port ' + _modalPort + '?')) return;

    document.getElementById('mStatus').textContent = 'Closing all...';
    document.getElementById('mStatus').style.color = '#f0883e';

    fetch('/api/port-close-all/' + _modalPort, { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function(d) {
            document.getElementById('mStatus').textContent = 'Closed ' + (d.closed || 0) + ' positions';
            document.getElementById('mStatus').style.color = '#3fb950';
            openModal(_modalPort);
        })
        .catch(function(e) {
            document.getElementById('mStatus').textContent = 'Error: ' + e.message;
            document.getElementById('mStatus').style.color = '#f85149';
        });
}

function closeSingleTrade(tradeId) {
    if (!_modalPort) return;
    if (!confirm('Close this position?')) return;

    fetch('/api/port-close-trade/' + _modalPort + '/' + tradeId, { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function() { openModal(_modalPort); })
        .catch(function(e) { alert('Error: ' + e.message); });
}

document.getElementById('startDate').addEventListener('change', refresh);
refresh();
setInterval(refresh, 30000);
</script>
</body>
</html>"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=1111, debug=False)
