"""Multi-Strategy Dashboard - Port 1111"""
import json
import time
import os
import logging
from functools import wraps
from flask import Flask, jsonify, request, Response

logger = logging.getLogger(__name__)

def create_app(config, database, strategy_manager, detector_ref):
    app = Flask(__name__)
    password = config.get("dashboard", {}).get("password", "")

    def check_auth(username, pw):
        return username == "admin" and pw == password

    def requires_auth(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.authorization
            if password and (not auth or not check_auth(auth.username, auth.password)):
                return Response("Auth required", 401, {"WWW-Authenticate": 'Basic realm="Login"'})
            return f(*args, **kwargs)
        return decorated

    STRATEGY_IDS = list(config.get("strategies", {}).keys())

    @app.route("/")
    @requires_auth
    def index():
        tabs_html = ""
        for i, sid in enumerate(STRATEGY_IDS):
            s = strategy_manager.get_strategy(sid)
            active_class = "active" if i == 0 else ""
            status_dot = '<span style="color:#3fb950">&#9679;</span>' if s and s.active else '<span style="color:#8b949e">&#9679;</span>'
            tabs_html += f'<button class="tab-btn {active_class}" onclick="switchTab(\'{sid}\')" id="tab-{sid}">{status_dot} {sid}</button>'

        return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Multi-Strategy Dashboard</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#0d1117; color:#c9d1d9; font-family:'Segoe UI',sans-serif; }}
.header {{ background:#161b22; padding:12px 20px; border-bottom:1px solid #30363d; display:flex; align-items:center; justify-content:space-between; }}
.header h1 {{ font-size:18px; color:#f0f6fc; }}
.header .mode {{ background:#238636; color:#fff; padding:4px 12px; border-radius:12px; font-size:12px; font-weight:600; }}
.tabs {{ display:flex; gap:4px; padding:8px 20px; background:#161b22; border-bottom:1px solid #30363d; flex-wrap:wrap; }}
.tab-btn {{ background:#21262d; color:#8b949e; border:1px solid #30363d; padding:8px 16px; border-radius:6px 6px 0 0; cursor:pointer; font-size:13px; font-weight:600; transition:all 0.2s; }}
.tab-btn:hover {{ background:#30363d; color:#c9d1d9; }}
.tab-btn.active {{ background:#0d1117; color:#58a6ff; border-bottom-color:#0d1117; }}
.content {{ padding:20px; max-width:1400px; margin:0 auto; }}
.overview {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; margin-bottom:20px; }}
.overview-card {{ background:#161b22; border:1px solid #30363d; border-radius:8px; padding:12px; text-align:center; }}
.overview-card .label {{ font-size:11px; color:#8b949e; text-transform:uppercase; margin-bottom:4px; }}
.overview-card .value {{ font-size:20px; font-weight:700; }}
.strategy-panel {{ display:none; }}
.strategy-panel.active {{ display:block; }}
.settings-box {{ background:#161b22; border:1px solid #30363d; border-radius:8px; padding:16px; margin-bottom:16px; }}
.settings-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:10px; }}
.settings-grid label {{ font-size:11px; color:#8b949e; text-transform:uppercase; display:block; margin-bottom:4px; }}
.settings-grid input {{ width:100%; background:#0d1117; border:1px solid #30363d; color:#f0f6fc; padding:6px 8px; border-radius:4px; font-size:14px; }}
.btn {{ padding:8px 20px; border:none; border-radius:6px; cursor:pointer; font-weight:600; font-size:13px; }}
.btn-run {{ background:#238636; color:#fff; }}
.btn-run:hover {{ background:#2ea043; }}
.btn-stop {{ background:#da3633; color:#fff; }}
.btn-stop:hover {{ background:#f85149; }}
.btn-save {{ background:#1f6feb; color:#fff; margin-left:8px; }}
.btn-save:hover {{ background:#388bfd; }}
.btn-close-all {{ background:#b91c1c; color:#fff; margin-left:8px; }}
.stats-row {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:10px; margin:16px 0; }}
.stat-card {{ background:#161b22; border:1px solid #30363d; border-radius:8px; padding:10px; text-align:center; }}
.stat-card .label {{ font-size:10px; color:#8b949e; text-transform:uppercase; }}
.stat-card .value {{ font-size:16px; font-weight:700; margin-top:2px; }}
table {{ width:100%; border-collapse:collapse; margin-top:10px; }}
th {{ text-align:left; padding:8px; font-size:11px; color:#8b949e; border-bottom:1px solid #30363d; text-transform:uppercase; }}
td {{ padding:8px; font-size:13px; border-bottom:1px solid #21262d; }}
.pnl-pos {{ color:#3fb950; }}
.pnl-neg {{ color:#f85149; }}
.section-title {{ font-size:14px; font-weight:600; color:#f0f6fc; margin:16px 0 8px; }}
.signal-log {{ max-height:200px; overflow-y:auto; background:#0d1117; border:1px solid #30363d; border-radius:6px; padding:8px; font-size:12px; font-family:monospace; }}
</style>
</head><body>
<div class="header">
    <h1>Multi-Strategy Dashboard</h1>
    <div>
        <span id="wsStatus" style="color:#8b949e;font-size:12px">Connecting...</span>
        <span class="mode">DEMO</span>
    </div>
</div>
<div class="tabs" id="tabBar">{tabs_html}</div>
<div class="content">
    <div class="overview" id="overviewCards">
        <div class="overview-card"><div class="label">Active Strategies</div><div class="value" id="ovActive">0/6</div></div>
        <div class="overview-card"><div class="label">Total Open</div><div class="value" id="ovOpen">0</div></div>
        <div class="overview-card"><div class="label">Pumps Detected</div><div class="value" id="ovPumps">0</div></div>
        <div class="overview-card"><div class="label">Total PNL Today</div><div class="value" id="ovPnl">0.00</div></div>
        <div class="overview-card"><div class="label">Coins Monitored</div><div class="value" id="ovCoins">0</div></div>
    </div>
    <div id="strategyPanels"></div>
</div>
<script>
var currentTab = '{STRATEGY_IDS[0] if STRATEGY_IDS else ""}';
var STRATEGIES = {json.dumps(STRATEGY_IDS)};

function switchTab(sid) {{
    currentTab = sid;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('tab-'+sid).classList.add('active');
    document.querySelectorAll('.strategy-panel').forEach(p => p.classList.remove('active'));
    var panel = document.getElementById('panel-'+sid);
    if (panel) panel.classList.add('active');
    fetchStrategyData(sid);
}}

function formatNum(n, d) {{ d = d || 2; return (n||0).toFixed(d); }}
function formatTime(seconds) {{
    var h = Math.floor(seconds/3600);
    var m = Math.floor((seconds%3600)/60);
    var s = Math.floor(seconds%60);
    return h+'h '+m+'m '+s+'s';
}}

function buildPanels(data) {{
    var container = document.getElementById('strategyPanels');
    container.innerHTML = '';
    STRATEGIES.forEach(function(sid, idx) {{
        var info = data[sid] || {{}};
        var cfg = info.config || {{}};
        var stats = info.stats || {{}};
        var isActive = cfg.active || false;
        var panel = document.createElement('div');
        panel.id = 'panel-' + sid;
        panel.className = 'strategy-panel' + (idx === 0 ? ' active' : '');
        panel.innerHTML = '<div class="settings-box">' +
            '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">' +
            '<h2 style="font-size:16px;color:#f0f6fc">' + sid + ' - ' + (cfg.name||sid) + '</h2>' +
            '<div>' +
            '<button class="btn ' + (isActive ? 'btn-stop' : 'btn-run') + '" onclick="toggleStrategy(\\'' + sid + '\\',' + !isActive + ')">' + (isActive ? 'STOP' : 'RUN') + '</button>' +
            '<button class="btn btn-save" onclick="saveSettings(\\'' + sid + '\\')">SAVE</button>' +
            '<button class="btn btn-close-all" onclick="closeAll(\\'' + sid + '\\')">CLOSE ALL</button>' +
            '</div></div>' +
            '<div class="settings-grid">' +
            '<div><label>Take Profit (%)</label><input type="number" step="0.1" id="cfg-tp-'+sid+'" value="'+formatNum(cfg.pump_tp_percent,1)+'"></div>' +
            '<div><label>Stop Loss (%)</label><input type="number" step="0.1" id="cfg-sl-'+sid+'" value="'+formatNum(cfg.pump_sl_percent,1)+'"></div>' +
            '<div><label>Trade Amount (USDC)</label><input type="number" step="1" id="cfg-amount-'+sid+'" value="'+formatNum(cfg.trade_amount,1)+'"></div>' +
            '<div><label>Volume Spike (x)</label><input type="number" step="0.1" id="cfg-spike-'+sid+'" value="'+formatNum(cfg.volume_spike_multiplier,1)+'"></div>' +
            '<div><label>OB Buy Ratio (x)</label><input type="number" step="0.1" id="cfg-ob-'+sid+'" value="'+formatNum(cfg.orderbook_buy_ratio,1)+'"></div>' +
            '<div><label>Pump Window (s)</label><input type="number" step="10" id="cfg-window-'+sid+'" value="'+(cfg.pump_window_seconds||600)+'"></div>' +
            '<div><label>Max Trades</label><input type="number" step="1" id="cfg-max-'+sid+'" value="'+(cfg.max_trades||100)+'"></div>' +
            '<div><label>Max Duration (h)</label><input type="number" step="0.5" id="cfg-dur-'+sid+'" value="'+formatNum(cfg.max_duration_hours,1)+'"></div>' +
            '</div></div>' +
            '<div class="stats-row" id="stats-'+sid+'">' +
            '<div class="stat-card"><div class="label">Open</div><div class="value" id="st-open-'+sid+'">'+(stats.open_count||0)+'</div></div>' +
            '<div class="stat-card"><div class="label">Invested</div><div class="value" id="st-inv-'+sid+'">'+formatNum(stats.total_invested)+' USDC</div></div>' +
            '<div class="stat-card"><div class="label">Closed</div><div class="value" id="st-closed-'+sid+'">'+(stats.closed_count||0)+'</div></div>' +
            '<div class="stat-card"><div class="label">Win Rate</div><div class="value" id="st-wr-'+sid+'">'+formatNum(stats.win_rate,1)+'%</div></div>' +
            '<div class="stat-card"><div class="label">Realized PNL</div><div class="value" id="st-rpnl-'+sid+'">'+formatNum(stats.realized_pnl,4)+' USDC</div></div>' +
            '<div class="stat-card"><div class="label">PNL Today</div><div class="value" id="st-today-'+sid+'">'+formatNum(stats.pnl_today,4)+' USDC</div></div>' +
            '</div>' +
            '<div class="section-title">Open Positions</div>' +
            '<table><thead><tr><th>Symbol</th><th>Entry</th><th>Current</th><th>Amount</th><th>PNL %</th><th>PNL USDC</th><th>Duration</th><th>Action</th></tr></thead>' +
            '<tbody id="open-'+sid+'"><tr><td colspan="8" style="text-align:center;color:#8b949e">Loading...</td></tr></tbody></table>' +
            '<div class="section-title" style="margin-top:20px">Closed Trades (Last 50)</div>' +
            '<table><thead><tr><th>Symbol</th><th>Entry</th><th>Exit</th><th>PNL %</th><th>PNL USDC</th><th>Reason</th><th>Closed</th></tr></thead>' +
            '<tbody id="closed-'+sid+'"><tr><td colspan="7" style="text-align:center;color:#8b949e">Loading...</td></tr></tbody></table>';
        container.appendChild(panel);
    }});
    fetchStrategyData(currentTab);
}}

function fetchOverview() {{
    fetch('/api/overview').then(r=>r.json()).then(function(d) {{
        document.getElementById('ovActive').textContent = d.active_count + '/' + d.total_count;
        document.getElementById('ovOpen').textContent = d.total_open;
        document.getElementById('ovPumps').textContent = d.pumps_detected;
        document.getElementById('ovPnl').textContent = formatNum(d.total_pnl_today, 4) + ' USDC';
        document.getElementById('ovCoins').textContent = d.coins_monitored;
        document.getElementById('wsStatus').textContent = d.ws_connected ? 'Connected' : 'Disconnected';
        document.getElementById('wsStatus').style.color = d.ws_connected ? '#3fb950' : '#f85149';
        STRATEGIES.forEach(function(sid) {{
            var tab = document.getElementById('tab-'+sid);
            if (tab) {{
                var dot = d.strategy_active[sid] ? '<span style="color:#3fb950">&#9679;</span>' : '<span style="color:#8b949e">&#9679;</span>';
                tab.innerHTML = dot + ' ' + sid;
            }}
        }});
    }}).catch(function(){{}});
}}

function fetchStrategyData(sid) {{
    fetch('/api/strategy/'+sid+'/data').then(r=>r.json()).then(function(d) {{
        var stats = d.stats || {{}};
        var el = function(id) {{ return document.getElementById(id); }};
        if(el('st-open-'+sid)) el('st-open-'+sid).textContent = stats.open_count||0;
        if(el('st-inv-'+sid)) el('st-inv-'+sid).textContent = formatNum(stats.total_invested)+' USDC';
        if(el('st-closed-'+sid)) el('st-closed-'+sid).textContent = stats.closed_count||0;
        if(el('st-wr-'+sid)) el('st-wr-'+sid).textContent = formatNum(stats.win_rate,1)+'%';
        if(el('st-rpnl-'+sid)) {{
            var rpnl = stats.realized_pnl||0;
            el('st-rpnl-'+sid).textContent = (rpnl>=0?'+':'')+formatNum(rpnl,4)+' USDC';
            el('st-rpnl-'+sid).className = 'value '+(rpnl>=0?'pnl-pos':'pnl-neg');
        }}
        if(el('st-today-'+sid)) {{
            var tp = stats.pnl_today||0;
            el('st-today-'+sid).textContent = (tp>=0?'+':'')+formatNum(tp,4)+' USDC';
            el('st-today-'+sid).className = 'value '+(tp>=0?'pnl-pos':'pnl-neg');
        }}
        var now = Date.now()/1000;
        var openHtml = '';
        (d.open_trades||[]).forEach(function(t) {{
            var pnlClass = t.pnl_percent >= 0 ? 'pnl-pos' : 'pnl-neg';
            var dur = formatTime(now - t.entry_time);
            openHtml += '<tr><td>'+t.symbol+'</td><td>'+parseFloat(t.entry_price).toFixed(8)+'</td><td>'+parseFloat(t.current_price||0).toFixed(8)+'</td><td>'+formatNum(t.amount_usdc)+'</td><td class="'+pnlClass+'">'+formatNum(t.pnl_percent,2)+'%</td><td class="'+pnlClass+'">'+formatNum(t.pnl_usdc,4)+'</td><td>'+dur+'</td><td><button onclick="closeTrade('+t.id+')" style="background:#da3633;color:#fff;border:none;padding:3px 8px;border-radius:4px;cursor:pointer;font-size:11px">Close</button></td></tr>';
        }});
        if(!openHtml) openHtml = '<tr><td colspan="8" style="text-align:center;color:#8b949e">No open positions</td></tr>';
        if(el('open-'+sid)) el('open-'+sid).innerHTML = openHtml;
        var closedHtml = '';
        (d.closed_trades||[]).forEach(function(t) {{
            var pnlClass = t.pnl_percent >= 0 ? 'pnl-pos' : 'pnl-neg';
            closedHtml += '<tr><td>'+t.symbol+'</td><td>'+parseFloat(t.entry_price).toFixed(8)+'</td><td>'+parseFloat(t.exit_price||0).toFixed(8)+'</td><td class="'+pnlClass+'">'+formatNum(t.pnl_percent,2)+'%</td><td class="'+pnlClass+'">'+formatNum(t.pnl_usdc,4)+'</td><td>'+(t.close_reason||'')+'</td><td>'+(t.exit_time_str||'')+'</td></tr>';
        }});
        if(!closedHtml) closedHtml = '<tr><td colspan="7" style="text-align:center;color:#8b949e">No closed trades</td></tr>';
        if(el('closed-'+sid)) el('closed-'+sid).innerHTML = closedHtml;
    }}).catch(function(){{}});
}}

function toggleStrategy(sid, start) {{
    fetch('/api/strategy/'+sid+'/'+(start?'start':'stop'), {{method:'POST'}}).then(r=>r.json()).then(function() {{
        fetchOverview();
        location.reload();
    }});
}}

function saveSettings(sid) {{
    var data = {{
        pump_tp_percent: parseFloat(document.getElementById('cfg-tp-'+sid).value),
        pump_sl_percent: parseFloat(document.getElementById('cfg-sl-'+sid).value),
        trade_amount: parseFloat(document.getElementById('cfg-amount-'+sid).value),
        volume_spike_multiplier: parseFloat(document.getElementById('cfg-spike-'+sid).value),
        orderbook_buy_ratio: parseFloat(document.getElementById('cfg-ob-'+sid).value),
        pump_window_seconds: parseInt(document.getElementById('cfg-window-'+sid).value),
        max_trades: parseInt(document.getElementById('cfg-max-'+sid).value),
        max_duration_hours: parseFloat(document.getElementById('cfg-dur-'+sid).value)
    }};
    fetch('/api/strategy/'+sid+'/settings', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(data)}}).then(r=>r.json()).then(function(d) {{
        alert('Settings saved!');
    }});
}}

function closeTrade(tradeId) {{
    if(!confirm('Close this position?')) return;
    fetch('/api/trade/'+tradeId+'/close', {{method:'POST'}}).then(r=>r.json()).then(function() {{
        fetchStrategyData(currentTab);
    }});
}}

function closeAll(sid) {{
    if(!confirm('Close ALL positions for '+sid+'?')) return;
    if(!confirm('FINAL CONFIRMATION: Close ALL?')) return;
    fetch('/api/strategy/'+sid+'/close-all', {{method:'POST'}}).then(r=>r.json()).then(function(d) {{
        alert('Closed '+d.closed+' positions');
        fetchStrategyData(sid);
    }});
}}

fetch('/api/all-status').then(r=>r.json()).then(buildPanels);
setInterval(function() {{ fetchOverview(); fetchStrategyData(currentTab); }}, 5000);
fetchOverview();
</script>
</body></html>"""

    @app.route("/api/all-status")
    @requires_auth
    def api_all_status():
        return jsonify(strategy_manager.get_all_status())

    @app.route("/api/overview")
    @requires_auth
    def api_overview():
        status = strategy_manager.get_all_status()
        active_count = sum(1 for s in status.values() if s["active"])
        total_open = sum(s["stats"]["open_count"] for s in status.values())
        total_pnl_today = sum(s["stats"]["pnl_today"] for s in status.values())
        det = detector_ref[0] if detector_ref else None
        strategy_active = {sid: s["active"] for sid, s in status.items()}
        return jsonify({
            "active_count": active_count,
            "total_count": len(status),
            "total_open": total_open,
            "total_pnl_today": round(total_pnl_today, 4),
            "pumps_detected": det.stats["pumps_detected"] if det else 0,
            "coins_monitored": det.stats["symbols_monitored"] if det else 0,
            "ws_connected": det.stats["ws_connected"] if det else False,
            "strategy_active": strategy_active
        })

    @app.route("/api/strategy/<sid>/data")
    @requires_auth
    def api_strategy_data(sid):
        s = strategy_manager.get_strategy(sid)
        if not s:
            return jsonify({"error": "not found"}), 404
        stats = database.get_strategy_stats(sid)
        open_trades = database.get_open_trades(sid)
        closed_trades = database.get_closed_trades(sid, limit=50)
        return jsonify({
            "config": s.get_config(),
            "stats": stats,
            "open_trades": open_trades,
            "closed_trades": closed_trades
        })

    @app.route("/api/strategy/<sid>/start", methods=["POST"])
    @requires_auth
    def api_start(sid):
        s = strategy_manager.get_strategy(sid)
        if s:
            s.start()
        return jsonify({"status": "started"})

    @app.route("/api/strategy/<sid>/stop", methods=["POST"])
    @requires_auth
    def api_stop(sid):
        s = strategy_manager.get_strategy(sid)
        if s:
            s.stop()
        return jsonify({"status": "stopped"})

    @app.route("/api/strategy/<sid>/settings", methods=["POST"])
    @requires_auth
    def api_settings(sid):
        s = strategy_manager.get_strategy(sid)
        if not s:
            return jsonify({"error": "not found"}), 404
        data = request.get_json()
        s.update_config(data)
        return jsonify({"status": "saved"})

    @app.route("/api/trade/<int:trade_id>/close", methods=["POST"])
    @requires_auth
    def api_close_trade(trade_id):
        trade = database.get_trade(trade_id)
        if not trade:
            return jsonify({"error": "not found"}), 404
        det = detector_ref[0] if detector_ref else None
        price = det.windows.get(trade["symbol"], None)
        close_price = price.current_price if price else trade.get("current_price") or trade["entry_price"]
        database.close_trade(trade_id, close_price, "MANUAL")
        return jsonify({"status": "closed", "price": close_price})

    @app.route("/api/strategy/<sid>/close-all", methods=["POST"])
    @requires_auth
    def api_close_all(sid):
        open_trades = database.get_open_trades(sid)
        closed = 0
        det = detector_ref[0] if detector_ref else None
        for t in open_trades:
            pw = det.windows.get(t["symbol"]) if det else None
            cp = pw.current_price if pw else t.get("current_price") or t["entry_price"]
            database.close_trade(t["id"], cp, "CLOSE_ALL")
            closed += 1
        return jsonify({"status": "ok", "closed": closed})

    return app
