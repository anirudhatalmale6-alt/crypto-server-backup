"""
dashboard.py - Flask web dashboard for viewing crashes and simulated trades.
"""

import os
import time
import json
import logging
from flask import Flask, render_template_string, jsonify, request

from database import Database

logger = logging.getLogger(__name__)

# HTML template for the dashboard
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crypto Crash Detector (Crash Only)</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            min-height: 100vh;
        }
        .header {
            background: #161b22;
            border-bottom: 1px solid #30363d;
            padding: 16px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .header h1 {
            font-size: 20px;
            color: #f0f6fc;
        }
        .header .status {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
        }
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #3fb950;
            animation: pulse 2s infinite;
        }
        .status-dot.offline { background: #f85149; animation: none; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 24px; }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        .stat-card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 16px;
        }
        .stat-card .label {
            font-size: 12px;
            color: #8b949e;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }
        .stat-card .value {
            font-size: 24px;
            font-weight: 600;
            color: #f0f6fc;
        }
        .stat-card .value.positive { color: #3fb950; }
        .stat-card .value.negative { color: #f85149; }

        .section {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            margin-bottom: 24px;
            overflow: hidden;
        }
        .section-header {
            padding: 12px 16px;
            border-bottom: 1px solid #30363d;
            font-size: 14px;
            font-weight: 600;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .section-header .badge {
            background: #388bfd26;
            color: #58a6ff;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 12px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        th {
            text-align: left;
            padding: 8px 16px;
            background: #0d1117;
            color: #8b949e;
            font-weight: 500;
            border-bottom: 1px solid #30363d;
        }
        td {
            padding: 10px 16px;
            border-bottom: 1px solid #21262d;
        }
        tr:hover { background: #1c2128; }
        .pnl-positive { color: #3fb950; font-weight: 600; }
        .pnl-negative { color: #f85149; font-weight: 600; }
        .badge-open {
            background: #388bfd26; color: #58a6ff;
            padding: 2px 6px; border-radius: 4px; font-size: 11px;
        }
        .badge-closed {
            background: #21262d; color: #8b949e;
            padding: 2px 6px; border-radius: 4px; font-size: 11px;
        }
        .alert-row {
            background: #f8514922;
            animation: flash 1s ease-in-out 3;
        }
        @keyframes flash {
            0%, 100% { background: #f8514922; }
            50% { background: #f8514944; }
        }
        .empty-state {
            padding: 40px;
            text-align: center;
            color: #8b949e;
        }
        .refresh-note {
            font-size: 11px;
            color: #8b949e;
        }
        .config-info {
            font-size: 12px;
            color: #8b949e;
            padding: 8px 16px;
            border-top: 1px solid #21262d;
        }
        .settings-panel {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            margin-bottom: 24px;
            padding: 20px;
        }
        .settings-panel h2 {
            font-size: 16px;
            color: #f0f6fc;
            margin-bottom: 16px;
        }
        .settings-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 16px;
        }
        .setting-item label {
            display: block;
            font-size: 12px;
            color: #8b949e;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }
        .setting-item input, .setting-item select {
            width: 100%;
            padding: 8px 12px;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 6px;
            color: #f0f6fc;
            font-size: 14px;
        }
        .setting-item input:focus, .setting-item select:focus {
            outline: none;
            border-color: #58a6ff;
        }
        .btn-save {
            background: #238636;
            color: #fff;
            border: none;
            padding: 8px 24px;
            border-radius: 6px;
            font-size: 14px;
            cursor: pointer;
            font-weight: 600;
        }
        .btn-save:hover { background: #2ea043; }
        .btn-save:disabled { background: #21262d; color: #8b949e; cursor: not-allowed; }
        .settings-msg {
            display: inline-block;
            margin-left: 12px;
            font-size: 13px;
            color: #3fb950;
        }
        .settings-msg.error { color: #f85149; }
        .settings-toggle {
            cursor: pointer;
            color: #58a6ff;
            font-size: 13px;
            user-select: none;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Crypto Crash Detector (Crash Only)</h1>
        <div class="status">
            <div class="status-dot" id="statusDot"></div>
            <span id="statusText">Connecting...</span>
            <span class="refresh-note">(auto-refresh 5s)</span>
        </div>
    </div>

    <div class="container">
        <!-- Settings Panel -->
        <div class="settings-panel">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                <h2>Settings</h2>
                <span class="settings-toggle" onclick="toggleSettings()">[ Show / Hide ]</span>
            </div>
            <div id="settingsBody">
                <div class="settings-grid">
                    <div class="setting-item">
                        <label>Crash Threshold (%)</label>
                        <input type="number" id="setThreshold" step="1" min="1" max="99" value="{{ threshold }}">
                    </div>
                    <div class="setting-item">
                        <label>Time Window (minutes)</label>
                        <input type="text" id="setWindows" value="{{ windows }}" placeholder="e.g. 7, 15">
                    </div>
                    <div class="setting-item">
                        <label>Trade Amount (USDT)</label>
                        <input type="number" id="setAmount" step="10" min="10" value="{{ amount }}">
                    </div>
                    <div class="setting-item">
                        <label>Take Profit (%)</label>
                        <input type="number" id="setTP" step="1" min="1" max="500" value="{{ tp }}">
                    </div>
                    <div class="setting-item">
                        <label>Stop Loss (%)</label>
                        <input type="number" id="setSL" step="1" min="1" max="100" value="{{ sl }}">
                    </div>
                    <div class="setting-item">
                        <label>Trading Mode</label>
                        <select id="setMode">
                            <option value="demo" {{ 'selected' if mode == 'demo' else '' }}>DEMO (Paper)</option>
                            <option value="live" {{ 'selected' if mode == 'live' else '' }}>LIVE (Real Orders)</option>
                        </select>
                    </div>
                    <div class="setting-item">
                        <label>Entry Strategy</label>
                        <select id="setEntry">
                            <option value="instant" {{ 'selected' if entry == 'instant' else '' }}>Instant Buy (at crash)</option>
                            <option value="reversal" {{ 'selected' if entry == 'reversal' else '' }}>Wait for Reversal</option>
                        </select>
                    </div>
                    <div class="setting-item">
                        <label>Double Bottom (optional)</label>
                        <select id="setDoubleBottom">
                            <option value="off" {{ 'selected' if not dbl_bottom else '' }}>OFF</option>
                            <option value="on" {{ 'selected' if dbl_bottom else '' }}>ON (+-3%, 120 days)</option>
                        </select>
                    </div>
                </div>
                <button class="btn-save" id="btnSave" onclick="saveSettings()">Save Settings</button>
                <span class="settings-msg" id="settingsMsg"></span>
            </div>
        </div>

        <!-- Stats Grid -->
        <div class="stats-grid" id="statsGrid">
            <div class="stat-card">
                <div class="label">Pairs Monitored</div>
                <div class="value" id="statPairs">--</div>
            </div>
            <div class="stat-card">
                <div class="label">Crashes (24h)</div>
                <div class="value" id="statCrashes">--</div>
            </div>
            <div class="stat-card">
                <div class="label">Open Positions</div>
                <div class="value" id="statOpen">--</div>
            </div>
            <div class="stat-card">
                <div class="label">Total Invested</div>
                <div class="value" id="statInvested">--</div>
            </div>
            <div class="stat-card">
                <div class="label">Unrealized P&L</div>
                <div class="value" id="statUnrealized">--</div>
            </div>
            <div class="stat-card">
                <div class="label">Realized P&L</div>
                <div class="value" id="statRealized">--</div>
            </div>
            <div class="stat-card">
                <div class="label">Win Rate</div>
                <div class="value" id="statWinRate">--</div>
            </div>
            <div class="stat-card">
                <div class="label">Uptime</div>
                <div class="value" id="statUptime">--</div>
            </div>
        </div>

        <!-- Top Drops (Live) -->
        <div class="section">
            <div class="section-header">
                <span>Top Drops Right Now (all coins, live)</span>
                <span class="badge" id="topDropsCount">0</span>
            </div>
            <div id="topDropsTable">
                <div class="empty-state">Collecting price data... (wait 1-2 minutes after startup)</div>
            </div>
        </div>

        <!-- Historical Scanner -->
        <div class="settings-panel">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                <h2>Historical Scanner</h2>
                <span class="settings-toggle" onclick="toggleHistory()">[ Show / Hide ]</span>
            </div>
            <div id="historyBody" style="display:none">
                <div class="settings-grid">
                    <div class="setting-item">
                        <label>Date From</label>
                        <input type="date" id="histFrom">
                    </div>
                    <div class="setting-item">
                        <label>Date To</label>
                        <input type="date" id="histTo">
                    </div>
                    <div class="setting-item">
                        <label>Min Drop (%)</label>
                        <input type="number" id="histThreshold" step="1" min="1" max="99" value="20">
                    </div>
                    <div class="setting-item">
                        <label>Time Window (minutes)</label>
                        <select id="histWindow">
                            <option value="5">5 min</option>
                            <option value="15" selected>15 min</option>
                            <option value="30">30 min</option>
                            <option value="60">1 hour</option>
                            <option value="240">4 hours</option>
                            <option value="1440">1 day</option>
                        </select>
                    </div>
                    <div class="setting-item">
                        <label>Top N coins to scan</label>
                        <input type="number" id="histCount" step="10" min="10" max="500" value="100">
                    </div>
                </div>
                <button class="btn-save" id="btnScan" onclick="scanHistory()">Scan Historical Data</button>
                <span class="settings-msg" id="histMsg"></span>
                <div id="histResults" style="margin-top:16px"></div>
            </div>
        </div>

        <!-- Backtest -->
        <div class="settings-panel">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                <h2>Strategy Backtest</h2>
                <span class="settings-toggle" onclick="toggleBacktest()">[ Show / Hide ]</span>
            </div>
            <div id="backtestBody" style="display:none">
                <div style="display:flex;gap:8px;align-items:center;margin-bottom:12px">
                    <select id="btPreset" style="padding:6px 10px;background:#1a1a2e;color:#e0e0e0;border:1px solid #333;border-radius:4px">
                        <option value="">-- Presets --</option>
                    </select>
                    <button class="btn-save" style="padding:6px 14px;font-size:12px" onclick="loadPreset()">Load</button>
                    <button class="btn-save" style="padding:6px 14px;font-size:12px;background:#2d6a4f" onclick="savePreset()">Save</button>
                    <button class="btn-save" style="padding:6px 14px;font-size:12px;background:#c0392b" onclick="deletePreset()">Delete</button>
                </div>
                <div class="settings-grid">
                    <div class="setting-item">
                        <label>Date From</label>
                        <input type="date" id="btFrom">
                    </div>
                    <div class="setting-item">
                        <label>Date To</label>
                        <input type="date" id="btTo">
                    </div>
                    <div class="setting-item">
                        <label>Crash Threshold (%)</label>
                        <input type="number" id="btThreshold" step="1" min="5" max="80" value="30">
                    </div>
                    <div class="setting-item">
                        <label>Time Window</label>
                        <select id="btWindow">
                            <option value="5">5 min</option>
                            <option value="15" selected>15 min</option>
                            <option value="60">1 hour</option>
                            <option value="240">4 hours</option>
                            <option value="1440">1 day</option>
                        </select>
                    </div>
                    <div class="setting-item">
                        <label>Take Profit (%)</label>
                        <input type="number" id="btTP" step="5" min="5" max="500" value="50">
                    </div>
                    <div class="setting-item">
                        <label>Stop Loss (%)</label>
                        <input type="number" id="btSL" step="5" min="5" max="100" value="20">
                    </div>
                    <div class="setting-item">
                        <label>Trade Amount (USDT)</label>
                        <input type="number" id="btAmount" step="100" min="100" value="1000">
                    </div>
                    <div class="setting-item">
                        <label>Max Simultaneous Trades</label>
                        <input type="number" id="btMaxTrades" step="1" min="1" max="100" value="10">
                    </div>
                    <div class="setting-item">
                        <label>Coins to test</label>
                        <input type="number" id="btCoins" step="10" min="10" max="500" value="100">
                    </div>
                    <div class="setting-item">
                        <label>Double Bottom Filter</label>
                        <select id="btDoubleBottom">
                            <option value="off" selected>OFF (all crashes)</option>
                            <option value="on">ON (only near prev lows)</option>
                        </select>
                    </div>
                </div>
                <button class="btn-save" id="btnBacktest" onclick="runBacktest()">Run Backtest</button>
                <span class="settings-msg" id="btMsg"></span>
                <div id="btSummary" style="margin-top:16px"></div>
                <div id="btResults" style="margin-top:8px"></div>
            </div>
        </div>

        <!-- Active Alerts -->
        <div class="section">
            <div class="section-header">
                <span>Recent Crashes (alerts triggered)</span>
                <span class="badge" id="crashCount">0</span>
            </div>
            <div id="crashTable">
                <div class="empty-state">No crashes detected yet. Monitoring...</div>
            </div>
        </div>

        <!-- Open Trades -->
        <div class="section">
            <div class="section-header">
                <span>Open Positions (Paper Trading)</span>
                <span class="badge" id="openCount">0</span>
            </div>
            <div id="openTradesTable">
                <div class="empty-state">No open positions</div>
            </div>
        </div>

        <!-- Closed Trades -->
        <div class="section">
            <div class="section-header">
                <span>Trade History</span>
                <span class="badge" id="closedCount">0</span>
            </div>
            <div id="closedTradesTable">
                <div class="empty-state">No completed trades</div>
            </div>
        </div>

        <div class="config-info">
            Detection: {{ threshold }}%+ drop within {{ windows }} min |
            Trade size: EUR {{ amount }} |
            TP: {{ tp }}% | SL: {{ sl }}%
        </div>
    </div>

    <script>
        function formatNumber(n, decimals=2) {
            if (n === null || n === undefined) return '--';
            return Number(n).toFixed(decimals);
        }
        function formatEur(n) {
            if (n === null || n === undefined) return '--';
            let prefix = n >= 0 ? '+' : '';
            return prefix + Number(n).toFixed(2) + ' EUR';
        }
        function formatUptime(seconds) {
            let h = Math.floor(seconds / 3600);
            let m = Math.floor((seconds % 3600) / 60);
            return h + 'h ' + m + 'm';
        }

        async function refresh() {
            try {
                let resp = await fetch('api/data?t=' + Date.now());
                let data = await resp.json();

                // Update status
                let dot = document.getElementById('statusDot');
                let txt = document.getElementById('statusText');
                if (data.stats.ws_connected) {
                    dot.className = 'status-dot';
                    txt.textContent = data.stats.symbols_monitored + ' pairs live';
                } else {
                    dot.className = 'status-dot offline';
                    txt.textContent = 'Disconnected';
                }

                // Stats
                document.getElementById('statPairs').textContent = data.stats.symbols_monitored;
                document.getElementById('statCrashes').textContent = data.crashes_24h;
                document.getElementById('statOpen').textContent = data.portfolio.open_count;
                document.getElementById('statInvested').textContent =
                    formatNumber(data.portfolio.total_invested) + ' EUR';

                let unr = document.getElementById('statUnrealized');
                unr.textContent = formatEur(data.portfolio.unrealized_pnl);
                unr.className = 'value ' + (data.portfolio.unrealized_pnl >= 0 ? 'positive' : 'negative');

                let real = document.getElementById('statRealized');
                real.textContent = formatEur(data.portfolio.realized_pnl);
                real.className = 'value ' + (data.portfolio.realized_pnl >= 0 ? 'positive' : 'negative');

                document.getElementById('statWinRate').textContent =
                    formatNumber(data.portfolio.win_rate, 1) + '%';
                document.getElementById('statUptime').textContent =
                    formatUptime(data.stats.uptime);

                // Top drops table
                if (data.top_drops && data.top_drops.length > 0) {
                    let tdDiv = document.getElementById('topDropsTable');
                    document.getElementById('topDropsCount').textContent = data.top_drops.length;
                    let html = '<table><tr><th>#</th><th>Pair</th><th>Drop</th><th>High</th><th>Current</th><th>Window</th></tr>';
                    data.top_drops.forEach((d, i) => {
                        let dropClass = d.drop >= 10 ? 'pnl-negative' : '';
                        html += `<tr>
                            <td>${i+1}</td>
                            <td><strong>${d.symbol}</strong></td>
                            <td class="${dropClass}">-${formatNumber(d.drop, 2)}%</td>
                            <td>${formatNumber(d.high, 8)}</td>
                            <td>${formatNumber(d.current, 8)}</td>
                            <td>${d.window}m</td>
                        </tr>`;
                    });
                    html += '</table>';
                    tdDiv.innerHTML = html;
                }

                // Crashes table
                let crashDiv = document.getElementById('crashTable');
                document.getElementById('crashCount').textContent = data.crashes.length;
                if (data.crashes.length > 0) {
                    let html = '<table><tr><th>Time</th><th>Pair</th><th>Drop</th><th>From</th><th>To</th><th>Window</th></tr>';
                    data.crashes.forEach(c => {
                        let cls = c.acknowledged ? '' : 'class="alert-row"';
                        html += `<tr ${cls}>
                            <td>${c.detected_at_str}</td>
                            <td><strong>${c.symbol}</strong></td>
                            <td class="pnl-negative">-${formatNumber(c.drop_percent, 1)}%</td>
                            <td>${formatNumber(c.price_start, 8)}</td>
                            <td>${formatNumber(c.price_end, 8)}</td>
                            <td>${c.time_window_min}m</td>
                        </tr>`;
                    });
                    html += '</table>';
                    crashDiv.innerHTML = html;
                } else {
                    crashDiv.innerHTML = '<div class="empty-state">No crashes detected yet. Monitoring...</div>';
                }

                // Open trades
                let openDiv = document.getElementById('openTradesTable');
                document.getElementById('openCount').textContent = data.open_trades.length;
                if (data.open_trades.length > 0) {
                    let html = '<table><tr><th>Time</th><th>Pair</th><th>Entry</th><th>Current</th><th>Amount</th><th>P&L</th></tr>';
                    data.open_trades.forEach(t => {
                        let pnlClass = t.pnl_percent >= 0 ? 'pnl-positive' : 'pnl-negative';
                        html += `<tr>
                            <td>${t.entry_time_str}</td>
                            <td><strong>${t.symbol}</strong></td>
                            <td>${formatNumber(t.entry_price, 8)}</td>
                            <td>${formatNumber(t.current_price, 8)}</td>
                            <td>${formatNumber(t.amount_eur)} EUR</td>
                            <td class="${pnlClass}">${formatNumber(t.pnl_percent, 2)}% (${formatEur(t.pnl_eur)})</td>
                        </tr>`;
                    });
                    html += '</table>';
                    openDiv.innerHTML = html;
                } else {
                    openDiv.innerHTML = '<div class="empty-state">No open positions</div>';
                }

                // Closed trades
                let closedDiv = document.getElementById('closedTradesTable');
                document.getElementById('closedCount').textContent = data.closed_trades.length;
                if (data.closed_trades.length > 0) {
                    let html = '<table><tr><th>Entry Time</th><th>Pair</th><th>Entry</th><th>Exit</th><th>Amount</th><th>P&L</th><th>Status</th></tr>';
                    data.closed_trades.forEach(t => {
                        let pnlClass = t.pnl_percent >= 0 ? 'pnl-positive' : 'pnl-negative';
                        html += `<tr>
                            <td>${t.entry_time_str}</td>
                            <td><strong>${t.symbol}</strong></td>
                            <td>${formatNumber(t.entry_price, 8)}</td>
                            <td>${formatNumber(t.exit_price, 8)}</td>
                            <td>${formatNumber(t.amount_eur)} EUR</td>
                            <td class="${pnlClass}">${formatNumber(t.pnl_percent, 2)}% (${formatEur(t.pnl_eur)})</td>
                            <td><span class="badge-closed">CLOSED</span></td>
                        </tr>`;
                    });
                    html += '</table>';
                    closedDiv.innerHTML = html;
                } else {
                    closedDiv.innerHTML = '<div class="empty-state">No completed trades</div>';
                }

            } catch (e) {
                document.getElementById('statusDot').className = 'status-dot offline';
                document.getElementById('statusText').textContent = 'Dashboard error';
            }
        }

        // Set default dates for historical scanner + backtest
        (function() {
            let today = new Date();
            let weekAgo = new Date(today);
            weekAgo.setDate(weekAgo.getDate() - 7);
            let monthAgo = new Date(today);
            monthAgo.setDate(monthAgo.getDate() - 30);
            document.getElementById('histTo').value = today.toISOString().split('T')[0];
            document.getElementById('histFrom').value = weekAgo.toISOString().split('T')[0];
            document.getElementById('btTo').value = today.toISOString().split('T')[0];
            document.getElementById('btFrom').value = monthAgo.toISOString().split('T')[0];
        })();

        function toggleHistory() {
            let body = document.getElementById('historyBody');
            body.style.display = body.style.display === 'none' ? 'block' : 'none';
        }

        async function scanHistory() {
            let btn = document.getElementById('btnScan');
            let msg = document.getElementById('histMsg');
            let results = document.getElementById('histResults');
            btn.disabled = true;
            msg.textContent = 'Scanning... this may take 1-2 minutes for many coins...';
            msg.className = 'settings-msg';
            results.innerHTML = '';

            let payload = {
                date_from: document.getElementById('histFrom').value,
                date_to: document.getElementById('histTo').value,
                threshold: parseFloat(document.getElementById('histThreshold').value),
                window_minutes: parseInt(document.getElementById('histWindow').value),
                top_n: parseInt(document.getElementById('histCount').value)
            };

            try {
                let resp = await fetch('api/history/scan', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                let data = await resp.json();
                if (data.error) {
                    msg.textContent = 'Error: ' + data.error;
                    msg.className = 'settings-msg error';
                } else {
                    msg.textContent = `Found ${data.results.length} crashes in ${data.coins_scanned} coins (${data.scan_time_seconds}s)`;
                    if (data.results.length > 0) {
                        let html = '<table><tr><th>#</th><th>Pair</th><th>Date</th><th>Drop</th><th>High</th><th>Low</th><th>S</th><th>10C</th></tr>';
                        data.results.forEach((r, i) => {
                            let sStr = r.recovery_same > 0.5 ? `+${formatNumber(r.recovery_same, 1)}%` : 'No';
                            let sClass = r.recovery_same > 0.5 ? 'pnl-positive' : '';
                            let cStr = r.recovery_10c > 0.5 ? `+${formatNumber(r.recovery_10c, 1)}%` : 'No';
                            let cClass = r.recovery_10c > 0.5 ? 'pnl-positive' : '';
                            html += `<tr>
                                <td>${i+1}</td>
                                <td><strong>${r.symbol}</strong></td>
                                <td>${r.date}</td>
                                <td class="pnl-negative">-${formatNumber(r.drop_percent, 1)}%</td>
                                <td>${formatNumber(r.high_price, 8)}</td>
                                <td>${formatNumber(r.low_price, 8)}</td>
                                <td class="${sClass}">${sStr}</td>
                                <td class="${cClass}">${cStr}</td>
                            </tr>`;
                        });
                        html += '</table>';
                        results.innerHTML = html;
                    }
                }
            } catch(e) {
                msg.textContent = 'Scan failed: ' + e.message;
                msg.className = 'settings-msg error';
            }
            btn.disabled = false;
        }

        function toggleBacktest() {
            let body = document.getElementById('backtestBody');
            body.style.display = body.style.display === 'none' ? 'block' : 'none';
        }

        async function loadPresets() {
            try {
                let resp = await fetch('api/presets?t=' + Date.now());
                let presets = await resp.json();
                let sel = document.getElementById('btPreset');
                sel.innerHTML = '<option value="">-- Presets --</option>';
                Object.keys(presets).forEach(name => {
                    sel.innerHTML += '<option value="' + name + '">' + name + '</option>';
                });
            } catch(e) {}
        }
        async function savePreset() {
            let name = document.getElementById('btPreset').value;
            if (!name) name = prompt('Preset name (e.g. Setting 1):');
            if (!name) return;
            let preset = {
                threshold: parseFloat(document.getElementById('btThreshold').value),
                window_minutes: parseInt(document.getElementById('btWindow').value),
                take_profit: parseFloat(document.getElementById('btTP').value),
                stop_loss: parseFloat(document.getElementById('btSL').value),
                amount: parseFloat(document.getElementById('btAmount').value),
                max_simultaneous: parseInt(document.getElementById('btMaxTrades').value),
                top_n: parseInt(document.getElementById('btCoins').value),
                double_bottom: document.getElementById('btDoubleBottom').value
            };
            await fetch('api/presets', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:name, preset:preset})});
            await loadPresets();
            document.getElementById('btPreset').value = name;
            alert('Saved: ' + name);
        }
        async function loadPreset() {
            let name = document.getElementById('btPreset').value;
            if (!name) return;
            try {
                let resp = await fetch('api/presets?t=' + Date.now());
                let presets = await resp.json();
                let p = presets[name];
                if (!p) return;
                document.getElementById('btThreshold').value = p.threshold || 30;
                document.getElementById('btWindow').value = p.window_minutes || 15;
                document.getElementById('btTP').value = p.take_profit || 50;
                document.getElementById('btSL').value = p.stop_loss || 20;
                document.getElementById('btAmount').value = p.amount || 1000;
                document.getElementById('btMaxTrades').value = p.max_simultaneous || 10;
                document.getElementById('btCoins').value = p.top_n || 100;
                document.getElementById('btDoubleBottom').value = p.double_bottom || 'off';
            } catch(e) {}
        }
        async function deletePreset() {
            let name = document.getElementById('btPreset').value;
            if (!name) return;
            if (!confirm('Delete preset: ' + name + '?')) return;
            await fetch('api/presets', {method:'DELETE', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:name})});
            await loadPresets();
        }
        loadPresets();

        async function runBacktest() {
            let btn = document.getElementById('btnBacktest');
            let msg = document.getElementById('btMsg');
            let summary = document.getElementById('btSummary');
            let results = document.getElementById('btResults');
            btn.disabled = true;
            msg.textContent = 'Running backtest... this may take several minutes for long periods...';
            msg.className = 'settings-msg';
            summary.innerHTML = '';
            results.innerHTML = '';

            let payload = {
                date_from: document.getElementById('btFrom').value,
                date_to: document.getElementById('btTo').value,
                threshold: parseFloat(document.getElementById('btThreshold').value),
                window_minutes: parseInt(document.getElementById('btWindow').value),
                take_profit: parseFloat(document.getElementById('btTP').value),
                stop_loss: parseFloat(document.getElementById('btSL').value),
                amount: parseFloat(document.getElementById('btAmount').value),
                max_simultaneous: parseInt(document.getElementById('btMaxTrades').value),
                top_n: parseInt(document.getElementById('btCoins').value),
                double_bottom: document.getElementById('btDoubleBottom').value === 'on'
            };

            try {
                let resp = await fetch('api/backtest', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                let data = await resp.json();
                if (data.error) {
                    msg.textContent = 'Error: ' + data.error;
                    msg.className = 'settings-msg error';
                } else {
                    let s = data.summary;
                    msg.textContent = `Backtest complete: ${s.total_trades} trades in ${data.coins_scanned} coins (${data.scan_time_seconds}s)`;
                    let pnlClass = s.total_pnl >= 0 ? 'pnl-positive' : 'pnl-negative';
                    summary.innerHTML = `<div class="stats-grid" style="margin-top:8px">
                        <div class="stat-card"><div class="label">Total Trades</div><div class="value">${s.total_trades}</div></div>
                        <div class="stat-card"><div class="label">Win Rate</div><div class="value">${formatNumber(s.win_rate,1)}%</div></div>
                        <div class="stat-card"><div class="label">Total P&L</div><div class="value ${pnlClass}">${formatNumber(s.total_pnl,2)} USDT</div></div>
                        <div class="stat-card"><div class="label">Avg Win</div><div class="value pnl-positive">+${formatNumber(s.avg_win,2)}%</div></div>
                        <div class="stat-card"><div class="label">Avg Loss</div><div class="value pnl-negative">${formatNumber(s.avg_loss,2)}%</div></div>
                        <div class="stat-card"><div class="label">Best Trade</div><div class="value pnl-positive">+${formatNumber(s.best_trade,2)}%</div></div>
                        <div class="stat-card"><div class="label">Worst Trade</div><div class="value pnl-negative">${formatNumber(s.worst_trade,2)}%</div></div>
                        <div class="stat-card"><div class="label">Wins / Losses</div><div class="value">${s.wins} / ${s.losses}</div></div>
                        <div class="stat-card"><div class="label">Max Simultaneous</div><div class="value">${s.max_simultaneous || 0} trades</div></div>
                        <div class="stat-card"><div class="label">Max Capital Needed</div><div class="value">${formatNumber(s.max_capital_needed || 0, 0)} USDT</div></div>
                        <div class="stat-card"><div class="label">Trades Skipped</div><div class="value">${s.trades_skipped || 0}</div></div>
                        <div class="stat-card"><div class="label">Avg Duration</div><div class="value">${s.avg_duration_hours < 24 ? formatNumber(s.avg_duration_hours,1) + 'h' : formatNumber(s.avg_duration_hours/24,1) + 'd'}</div></div>
                    </div>`;
                    if (data.trades.length > 0) {
                        let html = '<table><tr><th>#</th><th>Pair</th><th>Entry Date</th><th>Exit Date</th><th>Duration</th><th>Entry</th><th>Exit</th><th>P&L %</th><th>P&L USDT</th><th>Exit Reason</th></tr>';
                        data.trades.forEach((t, i) => {
                            let cls = t.pnl_pct >= 0 ? 'pnl-positive' : 'pnl-negative';
                            let dur = '';
                            if (t.exit_date && t.entry_date) {
                                let ms = new Date(t.exit_date) - new Date(t.entry_date);
                                let secs = Math.floor(ms / 1000);
                                let d = Math.floor(secs / 86400); secs %= 86400;
                                let h = Math.floor(secs / 3600); secs %= 3600;
                                let m = Math.floor(secs / 60); let s = secs % 60;
                                if (d > 0) dur = d + 'd ' + h + 'h ' + m + 'm';
                                else if (h > 0) dur = h + 'h ' + m + 'm ' + s + 's';
                                else if (m > 0) dur = m + 'm ' + s + 's';
                                else dur = s + 's';
                            }
                            html += `<tr>
                                <td>${i+1}</td>
                                <td><strong>${t.symbol}</strong></td>
                                <td>${t.entry_date}</td>
                                <td>${t.exit_date || '-'}</td>
                                <td>${dur}</td>
                                <td>${formatNumber(t.entry_price, 8)}</td>
                                <td>${formatNumber(t.exit_price, 8)}</td>
                                <td class="${cls}">${t.pnl_pct >= 0 ? '+' : ''}${formatNumber(t.pnl_pct, 2)}%</td>
                                <td class="${cls}">${t.pnl_usdt >= 0 ? '+' : ''}${formatNumber(t.pnl_usdt, 2)}</td>
                                <td>${t.exit_reason}</td>
                            </tr>`;
                        });
                        html += '</table>';
                        results.innerHTML = html;
                    }
                }
            } catch(e) {
                msg.textContent = 'Backtest failed: ' + e.message;
                msg.className = 'settings-msg error';
            }
            btn.disabled = false;
        }

        function toggleSettings() {
            let body = document.getElementById('settingsBody');
            body.style.display = body.style.display === 'none' ? 'block' : 'none';
        }

        async function saveSettings() {
            let btn = document.getElementById('btnSave');
            let msg = document.getElementById('settingsMsg');
            btn.disabled = true;
            msg.textContent = 'Saving...';
            msg.className = 'settings-msg';

            let windowsStr = document.getElementById('setWindows').value;
            let windows = windowsStr.split(',').map(w => parseFloat(w.trim())).filter(w => !isNaN(w) && w > 0);
            if (windows.length === 0) {
                msg.textContent = 'Invalid time windows';
                msg.className = 'settings-msg error';
                btn.disabled = false;
                return;
            }

            let payload = {
                drop_threshold_percent: parseFloat(document.getElementById('setThreshold').value),
                time_windows_minutes: windows,
                amount_per_trade_eur: parseFloat(document.getElementById('setAmount').value),
                take_profit_percent: parseFloat(document.getElementById('setTP').value),
                stop_loss_percent: parseFloat(document.getElementById('setSL').value),
                mode: document.getElementById('setMode').value,
                reversal_mode: document.getElementById('setEntry').value,
                double_bottom_enabled: document.getElementById('setDoubleBottom').value === 'on'
            };

            try {
                let resp = await fetch('api/settings', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                let result = await resp.json();
                if (result.success) {
                    msg.textContent = 'Settings saved and applied!';
                    msg.className = 'settings-msg';
                } else {
                    msg.textContent = 'Error: ' + (result.error || 'Unknown');
                    msg.className = 'settings-msg error';
                }
            } catch(e) {
                msg.textContent = 'Failed to save: ' + e.message;
                msg.className = 'settings-msg error';
            }
            btn.disabled = false;
        }

        // Refresh every 5 seconds
        refresh();
        setInterval(refresh, 5000);
    </script>
</body>
</html>
"""


def create_app(config: dict, database: Database, detector_ref: list) -> Flask:
    """Create and configure the Flask dashboard application."""

    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    detection_cfg = config.get("detection", {})
    trading_cfg = config.get("trading", {})

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

    @app.route("/")
    def index():
        """Render the main dashboard."""
        return render_template_string(
            DASHBOARD_HTML,
            threshold=detection_cfg.get("drop_threshold_percent", 30),
            windows=", ".join(str(w) for w in detection_cfg.get("time_windows_minutes", [7, 15])),
            amount=trading_cfg.get("amount_per_trade_eur", 1000),
            tp=trading_cfg.get("take_profit_percent", 50),
            sl=trading_cfg.get("stop_loss_percent", 20),
            mode=trading_cfg.get("mode", "demo"),
            entry=trading_cfg.get("reversal_mode", "instant"),
            dbl_bottom=trading_cfg.get("double_bottom_enabled", False)
        )

    @app.route("/api/data")
    def api_data():
        """Get all dashboard data in one call."""
        # Get detector stats
        stats = {
            "symbols_monitored": 0,
            "messages_received": 0,
            "crashes_detected": 0,
            "trades_opened": 0,
            "ws_connected": False,
            "uptime": 0
        }
        if detector_ref:
            detector = detector_ref[0]
            stats = dict(detector.stats)
            stats["uptime"] = time.time() - stats.get("start_time", time.time())

        # Get top drops from all monitored symbols (deduplicated by symbol)
        top_drops = []
        if detector_ref:
            detector = detector_ref[0]
            windows_min = detector.time_windows
            best_drops = {}
            for symbol, pw in detector.windows.items():
                for wm in windows_min:
                    result = pw.get_drop_percent(wm * 60)
                    if result and result[0] > 0.01:
                        if symbol not in best_drops or result[0] > best_drops[symbol]["drop"]:
                            best_drops[symbol] = {
                                "symbol": symbol,
                                "drop": round(result[0], 2),
                                "high": result[1],
                                "current": result[2],
                                "window": wm
                            }
            top_drops = sorted(best_drops.values(), key=lambda x: x["drop"], reverse=True)[:50]

        response = jsonify({
            "stats": stats,
            "top_drops": top_drops,
            "crashes": database.get_recent_crashes(50),
            "crashes_24h": database.get_crash_count_24h(),
            "open_trades": database.get_open_trades(),
            "closed_trades": database.get_closed_trades(50),
            "portfolio": database.get_portfolio_summary()
        })
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

    @app.route("/api/crashes")
    def api_crashes():
        """Get crash history."""
        limit = request.args.get("limit", 100, type=int)
        return jsonify(database.get_recent_crashes(limit))

    @app.route("/api/trades")
    def api_trades():
        """Get all trades."""
        return jsonify(database.get_all_trades())

    @app.route("/api/portfolio")
    def api_portfolio():
        """Get portfolio summary."""
        return jsonify(database.get_portfolio_summary())

    @app.route("/api/stats")
    def api_stats():
        """Get monitor statistics."""
        if detector_ref:
            detector = detector_ref[0]
            stats = dict(detector.stats)
            stats["uptime"] = time.time() - stats.get("start_time", time.time())
            return jsonify(stats)
        return jsonify({"error": "Monitor not started"})

    @app.route("/api/acknowledge/<int:crash_id>", methods=["POST"])
    def acknowledge(crash_id):
        """Acknowledge a crash alert."""
        database.acknowledge_crash(crash_id)
        return jsonify({"success": True})

    @app.route("/api/history/scan", methods=["POST"])
    def history_scan():
        """Scan historical Binance data for crashes."""
        import requests as req
        from datetime import datetime
        from concurrent.futures import ThreadPoolExecutor, as_completed

        try:
            data = request.get_json()
            date_from = data.get("date_from")
            date_to = data.get("date_to")
            threshold = float(data.get("threshold", 20))
            window_minutes = int(data.get("window_minutes", 15))
            top_n = min(int(data.get("top_n", 100)), 500)

            start_ts = int(datetime.strptime(date_from, "%Y-%m-%d").timestamp() * 1000)
            end_ts = int(datetime.strptime(date_to + " 23:59:59", "%Y-%m-%d %H:%M:%S").timestamp() * 1000)

            interval_map = {5: "5m", 15: "15m", 30: "30m", 60: "1h", 240: "4h", 1440: "1d"}
            interval = interval_map.get(window_minutes, "15m")

            rest_url = config.get("binance", {}).get("rest_url", "https://api.binance.com")
            quote = config.get("binance", {}).get("quote_asset", "USDT")

            scan_start = time.time()

            resp = req.get(f"{rest_url}/api/v3/ticker/24hr", timeout=30)
            tickers = resp.json()
            usdt_pairs = [t for t in tickers if t["symbol"].endswith(quote) and float(t["quoteVolume"]) > 0]
            usdt_pairs.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)
            symbols = [t["symbol"] for t in usdt_pairs[:top_n]]

            def scan_symbol(symbol):
                hits = []
                try:
                    all_klines = []
                    cur = start_ts
                    for _ in range(15):
                        r = req.get(f"{rest_url}/api/v3/klines", params={
                            "symbol": symbol, "interval": interval,
                            "startTime": cur, "endTime": end_ts, "limit": 1000
                        }, timeout=15)
                        chunk = r.json()
                        if not chunk or not isinstance(chunk, list):
                            break
                        all_klines.extend(chunk)
                        if len(chunk) < 1000:
                            break
                        cur = chunk[-1][0] + 1
                    klines = all_klines
                    if not klines:
                        return hits
                    for i in range(len(klines)):
                        high = float(klines[i][2])
                        low = float(klines[i][3])
                        if high == 0:
                            continue
                        close_price = float(klines[i][4])
                        drop = ((high - low) / high) * 100
                        if drop >= threshold:
                            recovery_same = ((close_price - low) / low * 100) if low > 0 else 0
                            best_recovery_price = close_price
                            for j in range(i + 1, min(i + 11, len(klines))):
                                future_high = float(klines[j][2])
                                if future_high > best_recovery_price:
                                    best_recovery_price = future_high
                            recovery_10c = ((best_recovery_price - low) / low * 100) if low > 0 else 0
                            ts = int(klines[i][0]) / 1000
                            hits.append({
                                "symbol": symbol,
                                "date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M"),
                                "drop_percent": round(drop, 2),
                                "high_price": high,
                                "low_price": low,
                                "close_price": close_price,
                                "recovery_same": round(recovery_same, 2),
                                "recovery_10c": round(recovery_10c, 2)
                            })
                except Exception:
                    pass
                return hits

            results = []
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = {executor.submit(scan_symbol, s): s for s in symbols}
                for future in as_completed(futures):
                    results.extend(future.result())

            results.sort(key=lambda x: x["drop_percent"], reverse=True)
            scan_time = round(time.time() - scan_start, 1)

            return jsonify({
                "results": results[:200],
                "coins_scanned": len(symbols),
                "total_found": len(results),
                "scan_time_seconds": scan_time
            })

        except Exception as e:
            logger.error(f"History scan error: {e}")
            return jsonify({"error": str(e)})

    @app.route("/api/presets", methods=["GET"])
    def get_presets():
        presets_path = os.path.join(os.path.dirname(config_path), "presets.json")
        try:
            with open(presets_path, "r") as f:
                return jsonify(json.load(f))
        except Exception:
            return jsonify({})

    @app.route("/api/presets", methods=["POST"])
    def save_preset():
        presets_path = os.path.join(os.path.dirname(config_path), "presets.json")
        data = request.get_json()
        name = data.get("name", "")
        preset = data.get("preset", {})
        if not name:
            return jsonify({"error": "No name"}), 400
        try:
            with open(presets_path, "r") as f:
                presets = json.load(f)
        except Exception:
            presets = {}
        presets[name] = preset
        with open(presets_path, "w") as f:
            json.dump(presets, f, indent=2)
        return jsonify({"success": True})

    @app.route("/api/presets", methods=["DELETE"])
    def delete_preset():
        presets_path = os.path.join(os.path.dirname(config_path), "presets.json")
        data = request.get_json()
        name = data.get("name", "")
        try:
            with open(presets_path, "r") as f:
                presets = json.load(f)
            presets.pop(name, None)
            with open(presets_path, "w") as f:
                json.dump(presets, f, indent=2)
        except Exception:
            pass
        return jsonify({"success": True})

    @app.route("/api/backtest", methods=["POST"])
    def backtest():
        """Run a strategy backtest on historical data."""
        import requests as req
        from datetime import datetime
        from concurrent.futures import ThreadPoolExecutor, as_completed

        try:
            data = request.get_json()
            date_from = data.get("date_from")
            date_to = data.get("date_to")
            threshold = float(data.get("threshold", 30))
            window_minutes = int(data.get("window_minutes", 15))
            take_profit = float(data.get("take_profit", 50))
            stop_loss = float(data.get("stop_loss", 20))
            amount = float(data.get("amount", 1000))
            top_n = min(int(data.get("top_n", 100)), 500)
            max_simultaneous_limit = int(data.get("max_simultaneous", 10))

            use_double_bottom = bool(data.get("double_bottom", False))

            start_ts = int(datetime.strptime(date_from, "%Y-%m-%d").timestamp() * 1000)
            end_ts = int(datetime.strptime(date_to + " 23:59:59", "%Y-%m-%d %H:%M:%S").timestamp() * 1000)

            rest_url = config.get("binance", {}).get("rest_url", "https://api.binance.com")
            quote = config.get("binance", {}).get("quote_asset", "USDT")

            interval_map = {5: "5m", 15: "15m", 60: "1h", 240: "4h", 1440: "1d"}
            interval = interval_map.get(window_minutes, "15m")

            scan_start = time.time()

            resp = req.get(f"{rest_url}/api/v3/ticker/24hr", timeout=30)
            tickers = resp.json()
            usdt_pairs = [t for t in tickers if t["symbol"].endswith(quote) and float(t["quoteVolume"]) > 0]
            usdt_pairs.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)
            symbols = [t["symbol"] for t in usdt_pairs[:top_n]]

            def fetch_klines_paginated(symbol, intv, ts_start, ts_end, max_pages=15):
                all_klines = []
                cur = ts_start
                for _ in range(max_pages):
                    r = req.get(f"{rest_url}/api/v3/klines", params={
                        "symbol": symbol, "interval": intv,
                        "startTime": cur, "endTime": ts_end, "limit": 1000
                    }, timeout=15)
                    chunk = r.json()
                    if not chunk or not isinstance(chunk, list):
                        break
                    all_klines.extend(chunk)
                    if len(chunk) < 1000:
                        break
                    cur = chunk[-1][0] + 1
                return all_klines

            def backtest_symbol(symbol):
                trades = []
                try:
                    klines = fetch_klines_paginated(symbol, interval, start_ts, end_ts)
                    if not klines:
                        return trades

                    daily_lows = []
                    if use_double_bottom:
                        try:
                            lookback_start = start_ts - 120 * 86400 * 1000
                            dk = fetch_klines_paginated(symbol, "1d", lookback_start, end_ts, max_pages=3)
                            if dk:
                                pd_list = [(float(k[3]), k[0] / 1000) for k in dk]
                                for idx in range(1, len(pd_list) - 1):
                                    if pd_list[idx][0] <= pd_list[idx-1][0] and pd_list[idx][0] <= pd_list[idx+1][0]:
                                        daily_lows.append(pd_list[idx])
                                if pd_list:
                                    abs_min = min(pd_list, key=lambda x: x[0])
                                    if abs_min not in daily_lows:
                                        daily_lows.append(abs_min)
                        except Exception:
                            pass

                    in_trade = False
                    entry_price = 0
                    entry_date = ""

                    for i in range(len(klines)):
                        high = float(klines[i][2])
                        low = float(klines[i][3])
                        close = float(klines[i][4])
                        ts = int(klines[i][0]) / 1000

                        if in_trade:
                            pnl_high = ((high - entry_price) / entry_price) * 100
                            pnl_low = ((low - entry_price) / entry_price) * 100
                            candle_date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")

                            if pnl_high >= take_profit:
                                exit_price = entry_price * (1 + take_profit / 100)
                                pnl_usdt = amount * take_profit / 100
                                trades.append({
                                    "symbol": symbol,
                                    "entry_date": entry_date,
                                    "exit_date": candle_date,
                                    "entry_price": entry_price,
                                    "exit_price": round(exit_price, 8),
                                    "pnl_pct": round(take_profit, 2),
                                    "pnl_usdt": round(pnl_usdt, 2),
                                    "exit_reason": "TP"
                                })
                                in_trade = False
                            elif pnl_low <= -stop_loss:
                                exit_price = entry_price * (1 - stop_loss / 100)
                                pnl_usdt = -amount * stop_loss / 100
                                trades.append({
                                    "symbol": symbol,
                                    "entry_date": entry_date,
                                    "exit_date": candle_date,
                                    "entry_price": entry_price,
                                    "exit_price": round(exit_price, 8),
                                    "pnl_pct": round(-stop_loss, 2),
                                    "pnl_usdt": round(pnl_usdt, 2),
                                    "exit_reason": "SL"
                                })
                                in_trade = False
                        else:
                            if high == 0:
                                continue
                            drop = ((high - low) / high) * 100
                            if drop >= threshold:
                                if use_double_bottom and daily_lows:
                                    candle_ts = int(klines[i][0]) / 1000
                                    is_db = False
                                    for low_price, low_ts in daily_lows:
                                        if low_ts >= candle_ts - 3 * 86400:
                                            continue
                                        diff_pct = abs(low - low_price) / low_price * 100
                                        if diff_pct <= 3.0:
                                            is_db = True
                                            break
                                    if not is_db:
                                        continue

                                in_trade = True
                                entry_price = low
                                entry_date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")

                    if in_trade:
                        last_close = float(klines[-1][4])
                        pnl_pct = ((last_close - entry_price) / entry_price) * 100
                        pnl_usdt = amount * pnl_pct / 100
                        last_date = datetime.fromtimestamp(int(klines[-1][0]) / 1000).strftime("%Y-%m-%d %H:%M")
                        trades.append({
                            "symbol": symbol,
                            "entry_date": entry_date,
                            "exit_date": last_date,
                            "entry_price": entry_price,
                            "exit_price": round(last_close, 8),
                            "pnl_pct": round(pnl_pct, 2),
                            "pnl_usdt": round(pnl_usdt, 2),
                            "exit_reason": "OPEN"
                        })
                except Exception:
                    pass
                return trades

            all_trades = []
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = {executor.submit(backtest_symbol, s): s for s in symbols}
                for future in as_completed(futures):
                    all_trades.extend(future.result())

            all_trades.sort(key=lambda x: x["entry_date"])

            if max_simultaneous_limit > 0 and all_trades:
                filtered = []
                open_trades = []
                skipped = 0
                for t in all_trades:
                    open_trades = [ot for ot in open_trades if ot["exit_date"] > t["entry_date"]]
                    if len(open_trades) >= max_simultaneous_limit:
                        skipped += 1
                        continue
                    filtered.append(t)
                    open_trades.append(t)
                all_trades = filtered
                trades_skipped = skipped
            else:
                trades_skipped = 0

            max_simultaneous = 0
            if all_trades:
                events = []
                for t in all_trades:
                    events.append((t["entry_date"], 1))
                    events.append((t.get("exit_date", t["entry_date"]), -1))
                events.sort(key=lambda x: (x[0], x[1]))
                current_open = 0
                for _, delta in events:
                    current_open += delta
                    if current_open > max_simultaneous:
                        max_simultaneous = current_open

            durations = []
            for t in all_trades:
                if t.get("exit_date") and t.get("entry_date"):
                    try:
                        d1 = datetime.strptime(t["entry_date"], "%Y-%m-%d %H:%M")
                        d2 = datetime.strptime(t["exit_date"], "%Y-%m-%d %H:%M")
                        durations.append((d2 - d1).total_seconds() / 3600)
                    except Exception:
                        pass
            avg_duration_hours = round(sum(durations) / len(durations), 1) if durations else 0

            wins = [t for t in all_trades if t["pnl_pct"] > 0]
            losses = [t for t in all_trades if t["pnl_pct"] <= 0]
            total_pnl = sum(t["pnl_usdt"] for t in all_trades)

            summary = {
                "total_trades": len(all_trades),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": (len(wins) / len(all_trades) * 100) if all_trades else 0,
                "total_pnl": round(total_pnl, 2),
                "avg_win": round(sum(t["pnl_pct"] for t in wins) / len(wins), 2) if wins else 0,
                "avg_loss": round(sum(t["pnl_pct"] for t in losses) / len(losses), 2) if losses else 0,
                "best_trade": round(max(t["pnl_pct"] for t in all_trades), 2) if all_trades else 0,
                "worst_trade": round(min(t["pnl_pct"] for t in all_trades), 2) if all_trades else 0,
                "max_simultaneous": max_simultaneous,
                "max_capital_needed": round(max_simultaneous * amount, 2),
                "trades_skipped": trades_skipped,
                "avg_duration_hours": avg_duration_hours
            }

            scan_time = round(time.time() - scan_start, 1)

            return jsonify({
                "summary": summary,
                "trades": all_trades[:200],
                "coins_scanned": len(symbols),
                "scan_time_seconds": scan_time
            })

        except Exception as e:
            logger.error(f"Backtest error: {e}")
            return jsonify({"error": str(e)})

    @app.route("/api/settings", methods=["GET"])
    def get_settings():
        """Get current settings."""
        return jsonify({
            "drop_threshold_percent": detection_cfg.get("drop_threshold_percent", 30),
            "time_windows_minutes": detection_cfg.get("time_windows_minutes", [7, 15]),
            "amount_per_trade_eur": trading_cfg.get("amount_per_trade_eur", 1000),
            "take_profit_percent": trading_cfg.get("take_profit_percent", 50),
            "stop_loss_percent": trading_cfg.get("stop_loss_percent", 20),
            "mode": trading_cfg.get("mode", "demo")
        })

    @app.route("/api/settings", methods=["POST"])
    def save_settings():
        """Update settings live and save to config.json."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "error": "No data received"})

            if "drop_threshold_percent" in data:
                val = float(data["drop_threshold_percent"])
                detection_cfg["drop_threshold_percent"] = val
                if detector_ref:
                    detector_ref[0].drop_threshold = val

            if "time_windows_minutes" in data:
                val = data["time_windows_minutes"]
                detection_cfg["time_windows_minutes"] = val
                if detector_ref:
                    detector_ref[0].time_windows = val
                    detector_ref[0].max_window_seconds = max(val) * 60 + 60

            if "amount_per_trade_eur" in data:
                val = float(data["amount_per_trade_eur"])
                trading_cfg["amount_per_trade_eur"] = val
                if detector_ref:
                    detector_ref[0].trade_amount = val

            if "take_profit_percent" in data:
                val = float(data["take_profit_percent"])
                trading_cfg["take_profit_percent"] = val
                if detector_ref:
                    detector_ref[0].take_profit = val

            if "stop_loss_percent" in data:
                val = float(data["stop_loss_percent"])
                trading_cfg["stop_loss_percent"] = val
                if detector_ref:
                    detector_ref[0].stop_loss = val

            if "mode" in data:
                trading_cfg["mode"] = data["mode"]
                if detector_ref:
                    detector_ref[0].live_mode = data["mode"] == "live"

            if "reversal_mode" in data:
                trading_cfg["reversal_mode"] = data["reversal_mode"]
                if detector_ref:
                    detector_ref[0].reversal_mode = data["reversal_mode"]

            if "double_bottom_enabled" in data:
                val = bool(data["double_bottom_enabled"])
                trading_cfg["double_bottom_enabled"] = val
                if detector_ref:
                    detector_ref[0].double_bottom_enabled = val

            # Save to config.json
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    full_config = json.load(f)
                full_config["detection"] = detection_cfg
                full_config["trading"] = trading_cfg
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(full_config, f, indent=4, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Failed to save config: {e}")

            logger.info(f"Settings updated: threshold={detection_cfg.get('drop_threshold_percent')}%, "
                        f"windows={detection_cfg.get('time_windows_minutes')}, "
                        f"amount={trading_cfg.get('amount_per_trade_eur')}")

            return jsonify({"success": True})

        except Exception as e:
            logger.error(f"Settings update error: {e}")
            return jsonify({"success": False, "error": str(e)})

    return app
