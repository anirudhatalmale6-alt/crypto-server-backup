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
    <title>Scalping Pump - USDC Live</title>
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
            position: sticky;
            top: 0;
            z-index: 100;
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
        [id^="section"] { scroll-margin-top: 70px; }
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
        <h1>Scalping Pump <span style="font-size:14px;color:#3fb950;font-weight:400">USDC Live</span></h1>
        <div class="status">
            <div id="tradingBadge" style="display:inline-flex;align-items:center;gap:6px;background:#1a2332;border:1px solid #238636;border-radius:16px;padding:4px 12px;margin-right:8px;font-size:12px;font-weight:600;color:#3fb950">
                <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#3fb950;animation:pulse 1.5s infinite"></span>
                <span id="tradingModeText">Paper Trading Active</span>
                <span id="tradingUptime" style="color:#8b949e;font-weight:400;margin-left:4px"></span>
            </div>
            <span id="activeConfig" style="font-size:11px;color:#8b949e;margin-right:10px"></span>
            <a href="#sectionSettings" style="color:#58a6ff;font-size:12px;text-decoration:none;margin-right:10px;padding:3px 8px;border:1px solid #30363d;border-radius:6px" onclick="document.getElementById('settingsBody').style.display='block'">Settings</a>
            <a href="#sectionResults" style="color:#58a6ff;font-size:12px;text-decoration:none;margin-right:10px;padding:3px 8px;border:1px solid #30363d;border-radius:6px">Results</a>
            <div class="status-dot" id="statusDot"></div>
            <span id="statusText">Connecting...</span>
            <span class="refresh-note">(auto-refresh 2s)</span>
        </div>
    </div>

    <div class="container">

        <!-- Scalping Pump Strategy Info -->
        <div class="settings-panel" style="border-color:#238636;margin-bottom:16px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                <h2 style="color:#3fb950">Scalping Pump Strategy</h2>
                <span style="font-size:12px;color:#8b949e">Volume spike + Order book confirmation &rarr; USDC spot buy</span>
            </div>
            <div style="background:#1c1208;border:1px solid #d29922;border-radius:8px;padding:10px 16px;margin-bottom:12px;display:flex;align-items:center;gap:10px">
                <span style="font-size:18px">&#9888;</span>
                <span style="color:#d29922;font-size:13px;font-weight:600">DO NOT CHANGE in Settings below: Entry Strategy (keep Instant Buy), Double Bottom (keep OFF), Pump Detection (keep OFF). These are controlled by the volume pump system.</span>
            </div>
            <div class="settings-grid" style="grid-template-columns:repeat(6,1fr)">
                <div><label>Volume Spike</label><div style="padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#58a6ff;font-weight:600">3x avg</div></div>
                <div><label>Order Book Ratio</label><div style="padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#58a6ff;font-weight:600">Buy 1.5x Sell</div></div>
                <div><label>Confirm Window</label><div style="padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#58a6ff;font-weight:600">5 seconds</div></div>
                <div><label>Pump Window</label><div style="padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#58a6ff;font-weight:600">600s (10 min)</div></div>
                <div><label>Take Profit</label><div style="padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#3fb950;font-weight:600">30%</div></div>
                <div><label>Stop Loss</label><div style="padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#f85149;font-weight:600">10%</div></div>
            </div>
            <div class="settings-grid" style="grid-template-columns:repeat(4,1fr);margin-top:8px">
                <div><label>Max Duration</label><div style="padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#f0f6fc;font-weight:600">2 hours</div></div>
                <div><label>Trade Amount</label><div style="padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#f0f6fc;font-weight:600" id="scalpAmount">10 USDC</div></div>
                <div><label>Max Positions</label><div style="padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#f0f6fc;font-weight:600">100</div></div>
                <div><label>Coins Monitored</label><div style="padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#f0f6fc;font-weight:600">300 (USDT &rarr; USDC)</div></div>
            </div>
        </div>

        <!-- Settings Panel -->
        <div class="settings-panel" id="sectionSettings">
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
                    <div class="setting-item">
                        <label>Pump Detection</label>
                        <select id="setPump">
                            <option value="off" {{ 'selected' if pump_mode == 'off' else '' }}>OFF</option>
                            <option value="on" {{ 'selected' if pump_mode == 'on' else '' }}>ON</option>
                            <option value="pump_only" {{ 'selected' if pump_mode == 'pump_only' else '' }}>ON (only pump)</option>
                        </select>
                    </div>
                    <div class="setting-item">
                        <label>Pump Threshold (%)</label>
                        <input type="number" id="setPumpThreshold" step="1" min="1" max="50" value="{{ pump_threshold }}">
                    </div>
                    <div class="setting-item">
                        <label>Pump Window (seconds)</label>
                        <input type="number" id="setPumpWindow" step="1" min="1" max="3600" value="{{ pump_window }}">
                    </div>
                    <div class="setting-item">
                        <label>Pump TP (%)</label>
                        <input type="number" id="setPumpTP" step="1" min="1" max="500" value="{{ pump_tp }}">
                    </div>
                    <div class="setting-item">
                        <label>Pump SL (%)</label>
                        <input type="number" id="setPumpSL" step="1" min="1" max="100" value="{{ pump_sl }}">
                    </div>
                    <div class="setting-item">
                        <label>Max Duration (hours)</label>
                        <input type="number" id="setMaxDuration" step="1" min="0" max="72" value="{{ max_duration }}">
                    </div>
                    <div class="setting-item">
                        <label>Coins to Monitor</label>
                        <input type="number" id="setCoins" step="10" min="10" max="500" value="{{ trading_coins }}">
                    </div>
                    <div class="setting-item">
                        <label>Max Simultaneous Trades</label>
                        <input type="number" id="setMaxTrades" step="1" min="0" max="500" value="{{ max_trades }}">
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
                <div class="label">UNREALIZED P&L</div>
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
            <div class="stat-card" style="border-color:#3fb950">
                <div class="label" style="color:#3fb950">USDC Balance</div>
                <div class="value" id="statUsdcBal" style="color:#3fb950">--</div>
            </div>
            <div class="stat-card" style="border-color:#a371f7">
                <div class="label" style="color:#a371f7">Total Portfolio</div>
                <div class="value" id="statPortfolio" style="color:#a371f7">--</div>
            </div>
            <div class="stat-card" style="border-color:#f0883e">
                <div class="label" style="color:#f0883e">PNL Today</div>
                <div class="value" id="statPnlToday">--</div>
            </div>
        </div>

        <!-- Portfolio Summary Bar -->
        <div class="stats-grid" style="margin-top: 8px; grid-template-columns: repeat(5, 1fr) auto;">
            <div class="stat-card">
                <div class="label">Open Positions</div>
                <div class="value" id="sumOpen">--</div>
            </div>
            <div class="stat-card">
                <div class="label">Total Invested</div>
                <div class="value" id="sumInvested">--</div>
            </div>
            <div class="stat-card">
                <div class="label">Current Value</div>
                <div class="value" id="sumValue">--</div>
            </div>
            <div class="stat-card">
                <div class="label">Total PnL</div>
                <div class="value" id="sumPnl">--</div>
            </div>
            <div class="stat-card">
                <div class="label">Total PnL BOOK</div>
                <div class="value" id="sumPnlBook">--</div>
            </div>
            <div class="stat-card" style="display:flex; align-items:center; justify-content:center;">
                <button onclick="closeAllPositions()" style="background:#e74c3c; color:#fff; border:none; padding:14px 28px; font-size:16px; font-weight:700; cursor:pointer; border-radius:6px; letter-spacing:1px;">CLOSE ALL</button>
            </div>
        </div>
        <div style="display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-top:8px; padding:10px 16px; background:#161b22; border:1px solid #30363d; border-radius:6px;">
            <span style="color:#c9d1d9;font-size:13px;font-weight:700;margin-right:4px;">CLOSE ALL WHEN</span>
            <div style="display:flex;align-items:center;gap:4px;">
                <label style="color:#3fb950;font-size:12px;white-space:nowrap;">TP Book USDC &ge;</label>
                <input id="condTpBook" type="number" step="0.01" min="0" style="width:80px;padding:4px 6px;background:#0d1117;border:1px solid #30363d;color:#c9d1d9;border-radius:4px;font-size:12px;" placeholder="0">
            </div>
            <div style="display:flex;align-items:center;gap:4px;">
                <label style="color:#f85149;font-size:12px;white-space:nowrap;">SL Book USDC &le; -</label>
                <input id="condSlBook" type="number" step="0.01" min="0" style="width:80px;padding:4px 6px;background:#0d1117;border:1px solid #30363d;color:#c9d1d9;border-radius:4px;font-size:12px;" placeholder="0">
            </div>
            <button id="condBtnOnce" onclick="activateCond('once')" style="background:#238636;color:#fff;border:none;padding:6px 14px;font-size:11px;font-weight:700;cursor:pointer;border-radius:4px;">ACTIVATE ONE TIME</button>
            <button id="condBtnAlways" onclick="activateCond('always')" style="background:#1f6feb;color:#fff;border:none;padding:6px 14px;font-size:11px;font-weight:700;cursor:pointer;border-radius:4px;">ACTIVATE ALWAYS</button>
            <button id="condBtnRandom" onclick="activateCond('random')" style="background:#a371f7;color:#fff;border:none;padding:6px 14px;font-size:11px;font-weight:700;cursor:pointer;border-radius:4px;">ACTIVATE ALWAYS +RANDOM</button>
            <button id="condBtnOff" onclick="deactivateCond()" style="background:#b91c1c;color:#fff;border:none;padding:6px 14px;font-size:11px;font-weight:700;cursor:pointer;border-radius:4px;display:none;">DEACTIVATE</button>
            <span id="condStatus" style="font-size:12px;color:#8b949e;"></span>
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
                        <label>Max Duration (hours)</label>
                        <input type="number" id="btMaxDuration" step="1" min="0" max="720" value="0" title="0 = no limit">
                    </div>
                    <div class="setting-item">
                        <label>Trade Amount (USDT)</label>
                        <input type="number" id="btAmount" step="100" min="100" value="1000">
                    </div>
                    <div class="setting-item">
                        <label>Max Simultaneous Trades</label>
                        <input type="number" id="btMaxTrades" step="1" min="1" max="500" value="100">
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
                    <div class="setting-item">
                        <label>Pump Detection</label>
                        <select id="btPumpEnabled">
                            <option value="off" selected>OFF (crash only)</option>
                            <option value="on">ON (crash + pump)</option>
                            <option value="pump_only">ON (only pump)</option>
                        </select>
                    </div>
                    <div class="setting-item">
                        <label>Pump TP (%)</label>
                        <input type="number" id="btPumpTP" step="5" min="1" max="500" value="30">
                    </div>
                    <div class="setting-item">
                        <label>Pump SL (%)</label>
                        <input type="number" id="btPumpSL" step="5" min="1" max="100" value="10">
                    </div>
                    <div class="setting-item">
                        <label>Backtest Mode</label>
                        <select id="btMode">
                            <option value="candle" selected>Candle (fast, all coins)</option>
                            <option value="hybrid">Hybrid (all coins, tick precision)</option>
                            <option value="tick">Tick-by-tick (precise, 20 coins)</option>
                        </select>
                    </div>
                    <div class="setting-item">
                        <label>Pump Threshold (%)</label>
                        <input type="number" id="btPumpThreshold" step="1" min="1" max="50" value="5">
                    </div>
                    <div class="setting-item">
                        <label>Pump Window (seconds)</label>
                        <input type="number" id="btPumpWindow" step="1" min="1" max="60" value="5">
                    </div>
                    <div class="setting-item">
                        <label>Coin Range (tick mode)</label>
                        <select id="btCoinRange">
                            <option value="0" selected>1-20 (top volume)</option>
                            <option value="20">21-40</option>
                            <option value="40">41-60</option>
                            <option value="60">61-80</option>
                            <option value="80">81-100</option>
                            <option value="100">101-120</option>
                            <option value="120">121-140</option>
                            <option value="140">141-160</option>
                            <option value="160">161-180</option>
                            <option value="180">181-200</option>
                            <option value="200">201-300</option>
                            <option value="300">301-500</option>
                        </select>
                    </div>
                </div>
                <button class="btn-save" id="btnBacktest" onclick="runBacktest()">Run Backtest</button>
                <button class="btn-save" id="btnPaperTrade" onclick="applyPaperTrading()" style="background:#1f6feb;margin-left:8px">Apply to Paper Trading</button>
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
        <div class="section" id="sectionResults">
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
        var prevTradeCount = -1;
        var prevClosedCount = -1;
        function playAlert(type) {
            try {
                var ctx = new (window.AudioContext || window.webkitAudioContext)();
                if (type === 'buy') {
                    [800, 1000, 1200].forEach(function(freq, i) {
                        var osc = ctx.createOscillator();
                        var gain = ctx.createGain();
                        osc.connect(gain);
                        gain.connect(ctx.destination);
                        osc.frequency.value = freq;
                        osc.type = 'sine';
                        gain.gain.value = 0.3;
                        osc.start(ctx.currentTime + i * 0.15);
                        osc.stop(ctx.currentTime + i * 0.15 + 0.12);
                    });
                } else {
                    var osc = ctx.createOscillator();
                    var gain = ctx.createGain();
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.frequency.value = 600;
                    osc.type = 'sine';
                    gain.gain.value = 0.25;
                    osc.start(ctx.currentTime);
                    osc.stop(ctx.currentTime + 0.4);
                }
            } catch(e) {}
        }
        function formatNumber(n, decimals=4) {
            if (n === null || n === undefined) return '--';
            return Number(n).toFixed(decimals);
        }
        function formatEur(n) {
            if (n === null || n === undefined) return '--';
            let prefix = n >= 0 ? '+' : '';
            return prefix + Number(n).toFixed(4) + ' EUR';
        }
        function formatUptime(seconds) {
            let h = Math.floor(seconds / 3600);
            let m = Math.floor((seconds % 3600) / 60);
            return h + 'h ' + m + 'm';
        }

        var _pageV = 3;
        async function refresh() {
            try {
                let resp = await fetch('api/data?t=' + Date.now());
                let data = await resp.json();
                if (data._v && data._v !== _pageV) { location.reload(); return; }

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
                var badge = document.getElementById('tradingBadge');
                var modeText = document.getElementById('tradingModeText');
                var uptimeEl = document.getElementById('tradingUptime');
                if (data.stats.trading_mode === 'live') {
                    badge.style.borderColor = '#f0883e';
                    badge.style.color = '#f0883e';
                    badge.querySelector('span').style.background = '#f0883e';
                    modeText.textContent = 'LIVE Trading Active';
                } else {
                    badge.style.borderColor = '#238636';
                    badge.style.color = '#3fb950';
                    badge.querySelector('span').style.background = '#3fb950';
                    modeText.textContent = 'Paper Trading Active';
                }
                if (data.stats.uptime) {
                    var s = Math.floor(data.stats.uptime);
                    var d = Math.floor(s / 86400); s %= 86400;
                    var h = Math.floor(s / 3600); s %= 3600;
                    var m = Math.floor(s / 60); s %= 60;
                    var parts = [];
                    if (d > 0) parts.push(d + 'd');
                    parts.push(h + 'h');
                    parts.push(m + 'm');
                    parts.push(s + 's');
                    uptimeEl.textContent = parts.join(' ');
                }
                if (data.stats.active_config) {
                    var c = data.stats.active_config;
                    document.getElementById('activeConfig').textContent =
                        c.threshold + '% | ' + c.windows.join(',') + 'm | TP:' + c.tp + '% SL:' + c.sl + '% | ' + c.amount + ' USDT | ' + c.coins + ' coins | Max:' + (c.max_trades > 0 ? c.max_trades + ' trades' : 'unlimited');
                }

                // Stats
                document.getElementById('statPairs').textContent = data.stats.symbols_monitored;
                document.getElementById('statCrashes').textContent = data.crashes_24h;
                document.getElementById('statOpen').textContent = data.portfolio.open_count;
                let invVal = data.portfolio_ext ? data.portfolio_ext.total_invested : data.portfolio.total_invested;
                document.getElementById('statInvested').textContent =
                    formatNumber(invVal) + ' USDC';

                let unr = document.getElementById('statUnrealized');
                let unrVal = data.portfolio_ext ? data.portfolio_ext.total_pnl : data.portfolio.unrealized_pnl;
                unr.textContent = (unrVal >= 0 ? '+' : '') + Number(unrVal).toFixed(4) + ' USDC';
                unr.className = 'value ' + (unrVal >= 0 ? 'positive' : 'negative');

                let real = document.getElementById('statRealized');
                let realVal = data.portfolio.realized_pnl;
                real.textContent = (realVal >= 0 ? '+' : '') + Number(realVal).toFixed(4) + ' USDC';
                real.className = 'value ' + (realVal >= 0 ? 'positive' : 'negative');

                document.getElementById('statWinRate').textContent =
                    formatNumber(data.portfolio.win_rate, 1) + '%';
                document.getElementById('statUptime').textContent =
                    formatUptime(data.stats.uptime);

                // USDC Balance
                if (data.usdc_balance !== undefined) {
                    document.getElementById("statUsdcBal").textContent = formatNumber(data.usdc_balance, 2) + " USDC";
                }

                // Total Portfolio
                if (data.total_portfolio) {
                    document.getElementById("statPortfolio").textContent = formatNumber(data.total_portfolio.usdc, 2) + " USDC";
                }

                // PNL Today
                if (data.pnl_today) {
                    var ptEl = document.getElementById("statPnlToday");
                    var ptVal = data.pnl_today.usdc || 0;
                    ptEl.textContent = (ptVal >= 0 ? "+" : "") + formatNumber(ptVal, 2) + " USDC (" + data.pnl_today.pct + "%)";
                    ptEl.style.color = ptVal >= 0 ? "#3fb950" : "#f85149";
                }

                // Summary bar (calculated from real-time open_trades data)
                if (data.open_trades) {
                    var ot = data.open_trades;
                    var invested = 0, value = 0, bookVal = 0;
                    ot.forEach(function(t) {
                        invested += t.quantity * t.entry_price;
                        value += t.quantity * (t.current_price || t.entry_price);
                        bookVal += t.quantity * (t.book_price || t.current_price || t.entry_price);
                    });
                    var pnl = value - invested;
                    var pnlBook = bookVal - invested;
                    document.getElementById("sumOpen").textContent = ot.length;
                    document.getElementById("sumInvested").textContent = formatNumber(invested, 4) + " USDC";
                    document.getElementById("sumValue").textContent = formatNumber(value, 4) + " USDC";
                    var pnlEl = document.getElementById("sumPnl");
                    pnlEl.textContent = (pnl >= 0 ? "+" : "") + formatNumber(pnl, 4) + " USDC";
                    pnlEl.style.color = pnl >= 0 ? "#3fb950" : "#f85149";
                    var bookEl = document.getElementById("sumPnlBook");
                    bookEl.textContent = (pnlBook >= 0 ? "+" : "") + formatNumber(pnlBook, 4) + " USDC";
                    bookEl.style.color = pnlBook >= 0 ? "#3fb950" : "#f85149";
                }

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
                if (prevTradeCount >= 0 && data.open_trades.length > prevTradeCount) {
                    playAlert('buy');
                }
                if (data.open_trades.length > 0) {
                    let html = '<div style="margin-bottom:8px"><button onclick="closeAllPositions()" style="background:#b91c1c;color:#fff;border:none;padding:8px 20px;font-size:13px;font-weight:700;cursor:pointer;border-radius:6px">CLOSE ALL POSITIONS</button></div>';
                    html += '<table><tr><th>Time</th><th>Pair</th><th>Entry</th><th>Current</th><th>Amount</th><th>P&L</th><th>Action</th></tr>';
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
                if (prevClosedCount >= 0 && data.closed_trades.length > prevClosedCount) {
                    playAlert('sell');
                }
                if (data.closed_trades.length > 0) {
                    let html = '<table><tr><th>Entry Time</th><th>Pair</th><th>Entry</th><th>Exit</th><th>Amount</th><th>P&L</th><th>Status</th></tr>';
                    data.closed_trades.forEach(t => {
                        let pnlClass = t.pnl_percent >= 0 ? 'pnl-positive' : 'pnl-negative';
                        html += `<tr>
                            <td>${t.entry_time_str}</td>
                            <td>${t.exit_time_str || "-"}</td>
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

                checkConditionalClose(data);
                prevTradeCount = data.open_trades.length;
                prevClosedCount = data.closed_trades.length;

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
                max_duration_hours: parseFloat(document.getElementById('btMaxDuration').value),
                amount: parseFloat(document.getElementById('btAmount').value),
                max_simultaneous: parseInt(document.getElementById('btMaxTrades').value),
                top_n: parseInt(document.getElementById('btCoins').value),
                double_bottom: document.getElementById('btDoubleBottom').value,
                pump_enabled: document.getElementById('btPumpEnabled').value,
                pump_tp: parseFloat(document.getElementById('btPumpTP').value),
                pump_sl: parseFloat(document.getElementById('btPumpSL').value),
                pump_threshold: parseFloat(document.getElementById('btPumpThreshold').value),
                pump_window_seconds: parseInt(document.getElementById('btPumpWindow').value)
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
                document.getElementById('btMaxDuration').value = p.max_duration_hours || 0;
                document.getElementById('btAmount').value = p.amount || 1000;
                document.getElementById('btMaxTrades').value = p.max_simultaneous || 10;
                document.getElementById('btCoins').value = p.top_n || 100;
                document.getElementById('btDoubleBottom').value = p.double_bottom || 'off';
                document.getElementById('btPumpEnabled').value = p.pump_enabled || 'off';
                document.getElementById('btPumpTP').value = p.pump_tp || 30;
                document.getElementById('btPumpSL').value = p.pump_sl || 10;
                document.getElementById('btPumpThreshold').value = p.pump_threshold || 5;
                document.getElementById('btPumpWindow').value = p.pump_window_seconds || 5;
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

        var lastHybridData = null;
        var lastPayload = null;

        window.refineWithTicks = refineWithTicks;
        async function refineWithTicks() {
            if (!lastHybridData || !lastPayload) { console.log('refine: no data', lastHybridData, lastPayload); return; }
            let msg = document.getElementById('btMsg');
            let summary = document.getElementById('btSummary');
            let results = document.getElementById('btResults');
            let refineBtn = document.getElementById('btnRefine');
            if (refineBtn) refineBtn.disabled = true;
            msg.textContent = 'Refining ' + lastHybridData.trades.length + ' trades with tick data... this may take ' + Math.ceil(lastHybridData.trades.length / 10 * 5 / 60) + '-' + Math.ceil(lastHybridData.trades.length / 10 * 15 / 60) + ' minutes...';
            msg.className = 'settings-msg';
            try {
                let resp = await fetch('api/backtest/refine', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        trades: lastHybridData.trades,
                        take_profit: lastPayload.take_profit,
                        stop_loss: lastPayload.stop_loss,
                        pump_tp: lastPayload.pump_tp,
                        pump_sl: lastPayload.pump_sl,
                        amount: lastPayload.amount,
                        max_duration_hours: lastPayload.max_duration_hours,
                        max_simultaneous: lastPayload.max_simultaneous,
                        window_minutes: lastPayload.window_minutes,
                        threshold: lastPayload.threshold,
                        pump_threshold: lastPayload.pump_threshold,
                        pump_window_seconds: lastPayload.pump_window_seconds
                    })
                });
                let data = await resp.json();
                if (data.error) {
                    msg.textContent = 'Refine error: ' + data.error;
                    msg.className = 'settings-msg error';
                } else {
                    let s = data.summary;
                    msg.textContent = 'Tick refinement complete: ' + s.total_trades + ' trades (' + data.scan_time_seconds + 's)';
                    let pnlClass = s.total_pnl >= 0 ? 'pnl-positive' : 'pnl-negative';
                    summary.innerHTML = '<div class="stats-grid" style="margin-top:8px">' +
                        '<div class="stat-card"><div class="label">Total Trades</div><div class="value">' + s.total_trades + '</div></div>' +
                        '<div class="stat-card"><div class="label">Win Rate</div><div class="value">' + formatNumber(s.win_rate,1) + '%</div></div>' +
                        '<div class="stat-card"><div class="label">Total P&L</div><div class="value ' + pnlClass + '">' + formatNumber(s.total_pnl,2) + ' USDT</div></div>' +
                        '<div class="stat-card"><div class="label">Avg Win</div><div class="value pnl-positive">+' + formatNumber(s.avg_win,2) + '%</div></div>' +
                        '<div class="stat-card"><div class="label">Avg Loss</div><div class="value pnl-negative">' + formatNumber(s.avg_loss,2) + '%</div></div>' +
                        '<div class="stat-card"><div class="label">' + (s.best_trade >= 0 ? 'Best' : 'Best') + ' Trade</div><div class="value ' + (s.best_trade >= 0 ? 'pnl-positive' : 'pnl-negative') + '">' + (s.best_trade >= 0 ? '+' : '') + formatNumber(s.best_trade,2) + '%</div></div>' +
                        '<div class="stat-card"><div class="label">Worst Trade</div><div class="value pnl-negative">' + formatNumber(s.worst_trade,2) + '%</div></div>' +
                        '<div class="stat-card"><div class="label">Wins / Losses</div><div class="value">' + s.wins + ' / ' + s.losses + '</div></div>' +
                        '<div class="stat-card"><div class="label">Crash / Pump</div><div class="value">' + (s.crash_trades||0) + ' / ' + (s.pump_trades||0) + '</div></div>' +
                        '<div class="stat-card"><div class="label">Max Simultaneous</div><div class="value">' + (s.max_simultaneous||0) + ' trades</div></div>' +
                        '<div class="stat-card"><div class="label">Max Capital Needed</div><div class="value">' + formatNumber(s.max_capital_needed||0, 0) + ' USDT</div></div>' +
                        '<div class="stat-card"><div class="label">Avg Duration</div><div class="value">' + (s.avg_duration_hours < 24 ? formatNumber(s.avg_duration_hours,1) + 'h' : formatNumber(s.avg_duration_hours/24,1) + 'd') + '</div></div>' +
                        '</div>';
                    if (data.trades.length > 0) {
                        let html = '<table><tr><th>#</th><th>Pair</th><th>Type</th><th>Entry Date</th><th>Exit Date</th><th>Duration</th><th>Entry</th><th>Exit</th><th>P&L %</th><th>P&L USDT</th><th>Exit Reason</th></tr>';
                        data.trades.forEach((t, i) => {
                            let cls = t.pnl_pct >= 0 ? 'pnl-positive' : 'pnl-negative';
                            let typeCls = t.entry_type === 'pump' ? 'color:#3fb950' : 'color:#f85149';
                            let typeLabel = (t.entry_type || 'crash').toUpperCase();
                            let dur = '';
                            if (t.exit_date && t.entry_date) {
                                let ms = new Date(t.exit_date) - new Date(t.entry_date);
                                let secs = Math.floor(ms / 1000);
                                let d = Math.floor(secs / 86400); secs %= 86400;
                                let h = Math.floor(secs / 3600); secs %= 3600;
                                let m = Math.floor(secs / 60); let s2 = secs % 60;
                                if (d > 0) dur = d + 'd ' + h + 'h ' + m + 'm';
                                else if (h > 0) dur = h + 'h ' + m + 'm ' + s2 + 's';
                                else if (m > 0) dur = m + 'm ' + s2 + 's';
                                else dur = s2 + 's';
                            }
                            html += '<tr><td>' + (i+1) + '</td><td><strong>' + t.symbol + '</strong></td><td style="' + typeCls + '">' + typeLabel + '</td><td>' + t.entry_date + '</td><td>' + (t.exit_date||'-') + '</td><td>' + dur + '</td><td>' + formatNumber(t.entry_price,8) + '</td><td>' + formatNumber(t.exit_price,8) + '</td><td class="' + cls + '">' + (t.pnl_pct>=0?'+':'') + formatNumber(t.pnl_pct,2) + '%</td><td class="' + cls + '">' + (t.pnl_usdt>=0?'+':'') + formatNumber(t.pnl_usdt,2) + '</td><td>' + t.exit_reason + '</td></tr>';
                        });
                        html += '</table>';
                        results.innerHTML = html;
                    }
                }
            } catch(e) {
                msg.textContent = 'Refine failed: ' + e.message;
                msg.className = 'settings-msg error';
            }
            if (refineBtn) refineBtn.disabled = false;
        }

        async function runBacktest() {
            let btn = document.getElementById('btnBacktest');
            let msg = document.getElementById('btMsg');
            let summary = document.getElementById('btSummary');
            let results = document.getElementById('btResults');
            btn.disabled = true;
            lastHybridData = null;
            msg.textContent = 'Running backtest... this may take several minutes for long periods...';
            msg.className = 'settings-msg';
            summary.innerHTML = '';
            results.innerHTML = '';

            lastPayload = {
                date_from: document.getElementById('btFrom').value,
                date_to: document.getElementById('btTo').value,
                threshold: parseFloat(document.getElementById('btThreshold').value),
                window_minutes: parseInt(document.getElementById('btWindow').value),
                take_profit: parseFloat(document.getElementById('btTP').value),
                stop_loss: parseFloat(document.getElementById('btSL').value),
                max_duration_hours: parseFloat(document.getElementById('btMaxDuration').value),
                amount: parseFloat(document.getElementById('btAmount').value),
                max_simultaneous: parseInt(document.getElementById('btMaxTrades').value),
                top_n: parseInt(document.getElementById('btCoins').value),
                double_bottom: document.getElementById('btDoubleBottom').value === 'on',
                pump_enabled: document.getElementById('btPumpEnabled').value,
                pump_tp: parseFloat(document.getElementById('btPumpTP').value),
                pump_sl: parseFloat(document.getElementById('btPumpSL').value),
                mode: document.getElementById('btMode').value,
                pump_threshold: parseFloat(document.getElementById('btPumpThreshold').value),
                pump_window_seconds: parseInt(document.getElementById('btPumpWindow').value),
                coin_range_start: parseInt(document.getElementById('btCoinRange').value)
            };
            let payload = lastPayload;
            if (payload.mode === 'tick') {
                payload.top_n = 20;
                msg.textContent = 'Running tick-by-tick backtest... this may take a few minutes...';
            } else if (payload.mode === 'hybrid') {
                msg.textContent = 'Running hybrid backtest... scanning all coins with candles, then minute precision for exits... this may take several minutes...';
            }

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
                        <div class="stat-card"><div class="label">Best Trade</div><div class="value ${s.best_trade >= 0 ? 'pnl-positive' : 'pnl-negative'}">${s.best_trade >= 0 ? '+' : ''}${formatNumber(s.best_trade,2)}%</div></div>
                        <div class="stat-card"><div class="label">Worst Trade</div><div class="value pnl-negative">${formatNumber(s.worst_trade,2)}%</div></div>
                        <div class="stat-card"><div class="label">Wins / Losses</div><div class="value">${s.wins} / ${s.losses}</div></div>
                        <div class="stat-card"><div class="label">Crash / Pump</div><div class="value">${s.crash_trades || 0} / ${s.pump_trades || 0}</div></div>
                        <div class="stat-card"><div class="label">Max Simultaneous</div><div class="value">${s.max_simultaneous || 0} trades</div></div>
                        <div class="stat-card"><div class="label">Max Capital Needed</div><div class="value">${formatNumber(s.max_capital_needed || 0, 0)} USDT</div></div>
                        <div class="stat-card"><div class="label">Trades Skipped</div><div class="value">${s.trades_skipped || 0}</div></div>
                        <div class="stat-card"><div class="label">Avg Duration</div><div class="value">${s.avg_duration_hours < 24 ? formatNumber(s.avg_duration_hours,1) + 'h' : formatNumber(s.avg_duration_hours/24,1) + 'd'}</div></div>
                    </div>`;
                    if (data.trades.length > 0) {
                        let html = '<table><tr><th>#</th><th>Pair</th><th>Type</th><th>Entry Date</th><th>Exit Date</th><th>Duration</th><th>Entry</th><th>Exit</th><th>P&L %</th><th>P&L USDT</th><th>Exit Reason</th></tr>';
                        data.trades.forEach((t, i) => {
                            let cls = t.pnl_pct >= 0 ? 'pnl-positive' : 'pnl-negative';
                            let typeCls = t.entry_type === 'pump' ? 'color:#3fb950' : 'color:#f85149';
                            let typeLabel = (t.entry_type || 'crash').toUpperCase();
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
                                <td style="${typeCls}">${typeLabel}</td>
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
                        if (payload.mode === 'hybrid' || payload.mode === 'candle') {
                            lastHybridData = data;
                            html += '<div style="margin-top:16px;text-align:center"><button id="btnRefine" style="background:#238636;color:#fff;border:none;padding:10px 24px;border-radius:6px;cursor:pointer;font-size:14px;font-weight:600">Refine with Tick-by-Tick Data</button></div>';
                        }
                        results.innerHTML = html;
                        var refBtn = document.getElementById('btnRefine');
                        if (refBtn) refBtn.addEventListener('click', refineWithTicks);
                    }
                }
            } catch(e) {
                msg.textContent = 'Backtest failed: ' + e.message;
                msg.className = 'settings-msg error';
            }
            btn.disabled = false;
        }

        async function applyPaperTrading() {
            let btn = document.getElementById('btnPaperTrade');
            let msg = document.getElementById('btMsg');
            btn.disabled = true;
            msg.textContent = 'Applying settings to paper trading...';
            msg.className = 'settings-msg';
            try {
                let payload = {
                    drop_threshold_percent: parseFloat(document.getElementById('btThreshold').value),
                    time_windows_minutes: [parseInt(document.getElementById('btWindow').value)],
                    take_profit_percent: parseFloat(document.getElementById('btTP').value),
                    stop_loss_percent: parseFloat(document.getElementById('btSL').value),
                    amount_per_trade_eur: parseFloat(document.getElementById('btAmount').value),
                    max_duration_hours: parseFloat(document.getElementById('btMaxDuration').value),
                    max_simultaneous_trades: parseInt(document.getElementById('btMaxTrades').value),
                    trading_pairs_limit: parseInt(document.getElementById('btCoins').value),
                    pump_mode: document.getElementById('btPumpEnabled').value,
                    pump_threshold_percent: parseFloat(document.getElementById('btPumpThreshold').value),
                    pump_window_seconds: parseInt(document.getElementById('btPumpWindow').value),
                    pump_tp: parseFloat(document.getElementById('btPumpTP').value),
                    pump_sl: parseFloat(document.getElementById('btPumpSL').value)
                };
                let resp = await fetch('api/settings', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                let data = await resp.json();
                if (data.success) {
                    msg.textContent = 'Settings applied! Monitor now using new parameters (live update, no restart needed).';
                    msg.className = 'settings-msg';
                } else {
                    msg.textContent = 'Error: ' + (data.error || 'Unknown');
                    msg.className = 'settings-msg error';
                }
            } catch(e) {
                msg.textContent = 'Failed: ' + e.message;
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
                double_bottom_enabled: document.getElementById('setDoubleBottom').value === 'on',
                pump_mode: document.getElementById('setPump').value,
                pump_threshold_percent: parseFloat(document.getElementById('setPumpThreshold').value),
                pump_window_seconds: parseInt(document.getElementById('setPumpWindow').value),
                pump_tp: parseFloat(document.getElementById('setPumpTP').value),
                pump_sl: parseFloat(document.getElementById('setPumpSL').value),
                max_duration_hours: parseFloat(document.getElementById('setMaxDuration').value),
                trading_pairs_limit: parseInt(document.getElementById('setCoins').value),
                max_simultaneous_trades: parseInt(document.getElementById('setMaxTrades').value)
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
        setInterval(refresh, 2000);
    
        async function closeSinglePosition(tradeId, symbol) {
            if (!confirm('Close ' + symbol + ' at current market price?')) return;
            try {
                let r = await fetch('/api/close-position/' + tradeId, {method: 'POST'});
                let d = await r.json();
                if (d.success) {
                    refresh();
                } else {
                    alert('Error: ' + (d.error || 'unknown'));
                }
            } catch(e) { alert('Error: ' + e.message); }
        }

        async function activateCond(mode) {
            var tp = parseFloat(document.getElementById('condTpBook').value) || 0;
            var sl = parseFloat(document.getElementById('condSlBook').value) || 0;
            if (tp <= 0 && sl <= 0) {
                alert('Set at least one value (TP Book or SL Book)');
                return;
            }
            try {
                let r = await fetch('/api/cond-state', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action: 'activate', mode: mode, tp: tp, sl: sl})
                });
                let d = await r.json();
                if (d.success) syncCondUI(d.state);
            } catch(e) { alert('Error: ' + e.message); }
        }

        async function deactivateCond() {
            try {
                let r = await fetch('/api/cond-state', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action: 'deactivate'})
                });
                let d = await r.json();
                if (d.success) syncCondUI(d.state);
            } catch(e) { alert('Error: ' + e.message); }
        }

        function syncCondUI(cs) {
            if (!cs) return;
            if (cs.active) {
                document.getElementById('condBtnOnce').style.display = 'none';
                document.getElementById('condBtnAlways').style.display = 'none';
                document.getElementById('condBtnRandom').style.display = 'none';
                document.getElementById('condBtnOff').style.display = '';
                if (cs.tp_base > 0) document.getElementById('condTpBook').value = cs.tp_base;
                if (cs.sl > 0) document.getElementById('condSlBook').value = cs.sl;
            } else {
                document.getElementById('condBtnOnce').style.display = '';
                document.getElementById('condBtnAlways').style.display = '';
                document.getElementById('condBtnRandom').style.display = '';
                document.getElementById('condBtnOff').style.display = 'none';
            }
            document.getElementById('condStatus').textContent = cs.status || 'Deactivated';
            document.getElementById('condStatus').style.color = cs.status_color || '#8b949e';
        }

        function checkConditionalClose(data) {
            if (data.cond_state) syncCondUI(data.cond_state);
        }

        async function closeAllPositions_auto() {
            try {
                let r = await fetch('/api/close-all', {method: 'POST'});
                let d = await r.json();
                if (d.success) {
                    refresh();
                }
            } catch(e) { console.error('Auto close error:', e); }
        }

        async function closeAllPositions() {
            if (!confirm('EMERGENCY CLOSE ALL - This will SELL ALL open positions on Binance at market price. Are you sure?')) return;
            if (!confirm('FINAL CONFIRMATION: Close ALL positions?')) return;
            try {
                let r = await fetch('/api/close-all', {method: 'POST'});
                let d = await r.json();
                if (d.success) {
                    showCloseAllResult(d);
                    refresh();
                } else {
                    alert('Error: ' + (d.error || 'unknown'));
                }
            } catch(e) { alert('Error: ' + e.message); }
        }

        function showCloseAllResult(d) {
            let pnlColor = d.total_pnl >= 0 ? '#3fb950' : '#f85149';
            let pnlSign = d.total_pnl >= 0 ? '+' : '';
            let modal = document.createElement('div');
            modal.id = 'closeAllModal';
            modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.85);z-index:99999;display:flex;align-items:center;justify-content:center';
            let box = document.createElement('div');
            box.style.cssText = 'background:#161b22;border:1px solid #30363d;border-radius:12px;padding:30px;min-width:420px;max-width:650px;max-height:80vh;overflow-y:auto;color:#c9d1d9;font-family:monospace';
            let h = '<h2 style="margin:0 0 20px;color:#c9d1d9;text-align:center;border-bottom:1px solid #30363d;padding-bottom:15px">CLOSE ALL - RESULT</h2>';
            h += '<div style="text-align:center;margin-bottom:20px">';
            h += '<div style="font-size:36px;font-weight:700;color:'+pnlColor+'">'+pnlSign+d.total_pnl.toFixed(4)+' USDC</div>';
            h += '<div style="font-size:13px;color:#8b949e;margin-top:5px">Realized P&L</div></div>';
            h += '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:20px">';
            h += '<div style="background:#0d1117;padding:10px;border-radius:8px;text-align:center"><div style="font-size:20px;font-weight:700">'+d.closed+'</div><div style="font-size:11px;color:#8b949e">Closed</div></div>';
            h += '<div style="background:#0d1117;padding:10px;border-radius:8px;text-align:center"><div style="font-size:20px;font-weight:700;color:#3fb950">'+d.wins+'</div><div style="font-size:11px;color:#8b949e">Profit</div></div>';
            h += '<div style="background:#0d1117;padding:10px;border-radius:8px;text-align:center"><div style="font-size:20px;font-weight:700;color:#f85149">'+d.losses+'</div><div style="font-size:11px;color:#8b949e">Loss</div></div></div>';
            h += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:20px">';
            h += '<div style="background:#0d1117;padding:10px;border-radius:8px;text-align:center"><div style="font-size:14px">'+d.total_invested.toFixed(2)+'</div><div style="font-size:11px;color:#8b949e">Invested USDC</div></div>';
            h += '<div style="background:#0d1117;padding:10px;border-radius:8px;text-align:center"><div style="font-size:14px">'+d.total_received.toFixed(2)+'</div><div style="font-size:11px;color:#8b949e">Received USDC</div></div></div>';
            if (d.best) h += '<div style="margin-bottom:6px;font-size:12px"><span style="color:#3fb950">Best:</span> '+d.best.symbol+' '+(d.best.pnl>=0?'+':'')+d.best.pnl.toFixed(4)+' USDC</div>';
            if (d.worst) h += '<div style="margin-bottom:15px;font-size:12px"><span style="color:#f85149">Worst:</span> '+d.worst.symbol+' '+(d.worst.pnl>=0?'+':'')+d.worst.pnl.toFixed(4)+' USDC</div>';
            if (d.failed > 0) h += '<div style="color:#f85149;margin-bottom:10px">Failed to close: '+d.failed+'</div>';
            h += '<div style="text-align:center;margin-top:15px"><button id="closeAllOk" style="background:#238636;color:#fff;border:none;padding:10px 30px;font-size:14px;font-weight:700;cursor:pointer;border-radius:6px">OK</button></div>';
            box.innerHTML = h;
            box.querySelector('#closeAllOk').onclick = function() { modal.remove(); };
            modal.appendChild(box);
            modal.onclick = function(e) { if (e.target === modal) modal.remove(); };
            document.body.appendChild(modal);
        }

        </script>
</body>
</html>
"""


import time as _time
import random as _random
_binance_cache = {"portfolio_ext": None, "usdc_balance": 0, "ts": 0, "open_books": {}, "fetching": False}
_cond_state = {"active": False, "mode": "off", "tp": 0, "tp_base": 0, "sl": 0, "cooldown": False, "status": "Deactivated", "status_color": "#8b949e"}


# Shared top-pairs cache (avoids ticker/24hr REST calls)
import sys as _sys_shared
if "/opt/crypto-shared" not in _sys_shared.path:
    _sys_shared.path.insert(0, "/opt/crypto-shared")
try:
    from shared_reader import get_top_pairs as _shared_get_top_pairs
except ImportError:
    _shared_get_top_pairs = None

def _get_cached_ticker_symbols(rest_url, quote="USDT", top_n=300, offset=0):
    """Get top symbols by volume from shared cache, REST fallback."""
    if _shared_get_top_pairs:
        cached = _shared_get_top_pairs(top_n + offset)
        if cached:
            result = [s.upper() for s in cached[offset:offset+top_n]]
            if result:
                return result
    import requests as _rq
    try:
        resp = _rq.get(f"{rest_url}/api/v3/ticker/24hr", timeout=30)
        if resp.status_code == 200:
            tickers = resp.json()
            usdt_pairs = [t for t in tickers if t["symbol"].endswith(quote) and float(t["quoteVolume"]) > 0]
            usdt_pairs.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)
            return [t["symbol"] for t in usdt_pairs[offset:offset+top_n]]
    except Exception:
        pass
    return []

def create_app(config: dict, database: Database, detector_ref: list) -> Flask:
    """Create and configure the Flask dashboard application."""

    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    def _parse_dt(s):
        from datetime import datetime
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")

    detection_cfg = config.get("detection", {})
    trading_cfg = config.get("trading", {})

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

    @app.after_request
    def add_no_cache(response):
        if response.content_type and 'text/html' in response.content_type:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

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
            dbl_bottom=trading_cfg.get("double_bottom_enabled", False),
            pump_mode='pump_only' if detection_cfg.get("pump_only") else ('on' if detection_cfg.get("pump_detection") else 'off'),
            pump_threshold=detection_cfg.get("pump_threshold_percent", 5),
            pump_window=detection_cfg.get("pump_window_seconds", 5),
            pump_tp=trading_cfg.get("pump_tp_percent", 30),
            pump_sl=trading_cfg.get("pump_sl_percent", 10),
            max_duration=trading_cfg.get("max_duration_hours", 0),
            trading_coins=config.get("binance", {}).get("top_pairs_count", 500),
            max_trades=trading_cfg.get("max_simultaneous_trades", 0)
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
            stats["trading_mode"] = "live" if detector.live_mode else "demo"
            stats["trading_enabled"] = detector.trading_enabled
            stats["active_config"] = {
                "threshold": detector.drop_threshold,
                "windows": detector.time_windows,
                "tp": detector.take_profit,
                "sl": detector.stop_loss,
                "amount": detector.trade_amount,
                "max_trades": detector.max_simultaneous_trades,
                "coins": detector.trading_pairs_limit
            }

        # Get top drops from all monitored symbols (deduplicated by symbol)
        top_drops = []
        if detector_ref:
            detector = detector_ref[0]
            windows_min = detector.time_windows
            best_drops = {}
            for symbol, pw in list(detector.windows.items()):
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

        open_trades = database.get_open_trades()
        closed_trades = database.get_closed_trades(50)
        resp_data = {
            "stats": stats,
            "top_drops": top_drops,
            "crashes": database.get_recent_crashes(50),
            "crashes_24h": database.get_crash_count_24h(),
            "open_trades": open_trades,
            "closed_trades": closed_trades,
            "portfolio": database.get_portfolio_summary()
        }

        # Portfolio ext + USDC balance with 60s cache to avoid Binance WAF
        global _binance_cache
        _now = _time.time()
        _cache_ttl = 30
        _eur_rate = 1.17

        if _now - _binance_cache["ts"] > _cache_ttl and not _binance_cache.get("fetching"):
            _binance_cache["fetching"] = True
            import requests as _req
            _rest = config.get("binance", {}).get("rest_url", "https://api.binance.com")
            _pext = {"open_count": len(open_trades), "total_invested": 0,
                     "current_value": 0, "total_pnl": 0, "pnl_book": 0, "eur_rate": _eur_rate}
            _new_books = {}
            _fetch_ok = True
            if open_trades:
                _pext["total_invested"] = sum(t["quantity"] * t["entry_price"] for t in open_trades)
                # Use WebSocket book prices (real-time, no REST calls)
                _ws_books = {}
                if detector_ref and len(detector_ref) >= 2:
                    _ws_books = getattr(detector_ref[1], "book_prices", {})
                    # Update which symbols to track
                    _open_syms = [t["symbol"] for t in open_trades]
                    if hasattr(detector_ref[1], "update_book_symbols"):
                        detector_ref[1].update_book_symbols(_open_syms)
                for t in open_trades:
                    cp = t.get("current_price") or t["entry_price"]
                    _pext["current_value"] += t["quantity"] * cp
                    _bp = _ws_books.get(t["symbol"])
                    if _bp and _bp.get("bid", 0) > 0:
                        _new_books[t["symbol"]] = _bp["bid"]
                    else:
                        _new_books[t["symbol"]] = _binance_cache.get("open_books", {}).get(t["symbol"], cp)
                _pext["current_value"] = round(_pext["current_value"], 2)
                _pext["total_pnl"] = round(_pext["current_value"] - _pext["total_invested"], 2)
                book_value = sum(t["quantity"] * _new_books.get(t["symbol"], t["entry_price"]) for t in open_trades)
                _pext["pnl_book"] = round(book_value - _pext["total_invested"], 2)

            _usdc = 0
            try:
                _trader = detector_ref[0].trader if detector_ref else None
                if _trader and _trader.live_mode:
                    _bal = _trader.get_account_balance("USDC")
                    _usdc = round(_bal, 2) if _bal is not None else _binance_cache.get("usdc_balance", 0)
            except Exception:
                _usdc = _binance_cache.get("usdc_balance", 0)

            _binance_cache["portfolio_ext"] = _pext
            _binance_cache["usdc_balance"] = _usdc
            _binance_cache["open_books"] = _new_books
            _binance_cache["ts"] = _now
            _binance_cache["fetching"] = False

        # Use cached values
        portfolio_ext = _binance_cache.get("portfolio_ext") or {"open_count": len(open_trades), "total_invested": 0, "current_value": 0, "total_pnl": 0, "pnl_book": 0, "eur_rate": _eur_rate}
        portfolio_ext["open_count"] = len(open_trades)
        for t in open_trades:
            t["book_price"] = _binance_cache.get("open_books", {}).get(t["symbol"], t.get("current_price", t["entry_price"]))
        resp_data["portfolio_ext"] = portfolio_ext
        resp_data["usdc_balance"] = _binance_cache.get("usdc_balance", 0)

        # Total portfolio + PNL today (from cached data, no Binance calls)
        try:
            import datetime as _dt
            usdc_bal = resp_data.get("usdc_balance", 0)
            open_value = sum(
                (t.get("current_price") or t.get("entry_price", 0)) * t.get("quantity", 0)
                for t in open_trades
            )
            total_usdc = usdc_bal + open_value
            resp_data["total_portfolio"] = {
                "usdc": round(total_usdc, 2),
                "eur": round(total_usdc / _eur_rate, 2) if _eur_rate > 0 else 0
            }
            today_str = _dt.date.today().isoformat()
            today_pnl = sum(
                t.get("pnl_eur", 0) for t in closed_trades
                if (t.get("exit_time_str") or "").startswith(today_str)
            )
            today_pnl_usdc = today_pnl
            pct = round(today_pnl_usdc / total_usdc * 100, 2) if total_usdc > 0 else 0
            resp_data["pnl_today"] = {
                "usdc": round(today_pnl_usdc, 2),
                "eur": round(today_pnl, 2),
                "pct": str(pct)
            }
        except Exception:
            pass

        # Server-side conditional close check
        global _cond_state
        if _cond_state["active"] and resp_data.get("portfolio_ext"):
            _pe = resp_data["portfolio_ext"]
            _book = _pe.get("pnl_book", 0)
            _oc = _pe.get("open_count", 0)
            if _cond_state["cooldown"]:
                if _oc > 0:
                    _cond_state["cooldown"] = False
                    _cond_state["status"] = f"Watching. TP>={_cond_state['tp']:.4f}" if _cond_state["tp"] > 0 else "Watching."
                    if _cond_state["sl"] > 0:
                        _cond_state["status"] += f" SL<=-{_cond_state['sl']:.4f}"
                    _cond_state["status_color"] = "#f0883e"
            elif _oc > 0:
                _triggered = False
                _reason = ""
                if _cond_state["tp"] > 0 and _book >= _cond_state["tp"]:
                    _triggered = True
                    _reason = f"TP TRIGGERED! Book={_book:.4f} USDC."
                    _cond_state["status_color"] = "#3fb950"
                if _cond_state["sl"] > 0 and _book <= -_cond_state["sl"]:
                    _triggered = True
                    _reason = f"SL TRIGGERED! Book={_book:.4f} USDC."
                    _cond_state["status_color"] = "#f85149"
                if _triggered:
                    try:
                        _trader = detector_ref[0].trader if detector_ref else None
                        _open = database.get_open_trades()
                        for _t in _open:
                            try:
                                if _trader and _trader.live_mode:
                                    _trader.sell(_t["symbol"], _t["quantity"])
                            except Exception:
                                pass
                            database.close_trade(_t["id"], _t.get("current_price") or _t["entry_price"])
                    except Exception:
                        pass
                    if _cond_state["mode"] == "once":
                        _cond_state["active"] = False
                        _cond_state["mode"] = "off"
                        _cond_state["cooldown"] = False
                        _cond_state["status"] = _reason + " Closed. (One time - deactivated)"
                    else:
                        _cond_state["cooldown"] = True
                        if _cond_state["mode"] == "random" and _cond_state["tp_base"] > 0:
                            _pct = 1 + (_random.random() * 9 + 1) / 100
                            _cond_state["tp"] = round(_cond_state["tp_base"] * _pct, 4)
                            _cond_state["status"] = _reason + f" Closed. Next TP={_cond_state['tp']:.4f}. Waiting..."
                        else:
                            _cond_state["status"] = _reason + " Closed. Waiting for next round..."

        resp_data["_v"] = 3
        resp_data["cond_state"] = {
            "active": _cond_state["active"],
            "mode": _cond_state["mode"],
            "tp": _cond_state["tp"],
            "tp_base": _cond_state["tp_base"],
            "sl": _cond_state["sl"],
            "cooldown": _cond_state["cooldown"],
            "status": _cond_state["status"],
            "status_color": _cond_state["status_color"]
        }

        response = jsonify(resp_data)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

    @app.route("/api/cond-state", methods=["GET"])
    def get_cond_state():
        global _cond_state
        return jsonify(_cond_state)

    @app.route("/api/cond-state", methods=["POST"])
    def set_cond_state():
        global _cond_state
        data = request.get_json()
        if data.get("action") == "activate":
            _cond_state["active"] = True
            _cond_state["mode"] = data.get("mode", "once")
            _cond_state["tp"] = float(data.get("tp", 0))
            _cond_state["tp_base"] = float(data.get("tp", 0))
            _cond_state["sl"] = float(data.get("sl", 0))
            _cond_state["cooldown"] = False
            if _cond_state["mode"] == "random" and _cond_state["tp_base"] > 0:
                _pct = 1 + (_random.random() * 9 + 1) / 100
                _cond_state["tp"] = round(_cond_state["tp_base"] * _pct, 4)
            label = {"once": "ONE TIME", "always": "ALWAYS", "random": "ALWAYS +RANDOM"}.get(_cond_state["mode"], _cond_state["mode"])
            msg = f"{label}: "
            if _cond_state["tp"] > 0:
                msg += f"TP >= {_cond_state['tp']:.4f} USDC"
                if _cond_state["mode"] == "random":
                    msg += f" (base {_cond_state['tp_base']:.4f} +1-10%)"
                msg += " "
            if _cond_state["sl"] > 0:
                msg += f"SL <= -{_cond_state['sl']:.4f} USDC"
            _cond_state["status"] = msg
            _cond_state["status_color"] = "#f0883e"
            return jsonify({"success": True, "state": _cond_state})
        elif data.get("action") == "deactivate":
            _cond_state["active"] = False
            _cond_state["mode"] = "off"
            _cond_state["tp"] = 0
            _cond_state["tp_base"] = 0
            _cond_state["sl"] = 0
            _cond_state["cooldown"] = False
            _cond_state["status"] = "Deactivated"
            _cond_state["status_color"] = "#8b949e"
            return jsonify({"success": True, "state": _cond_state})
        return jsonify({"error": "invalid action"}), 400

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

            symbols = _get_cached_ticker_symbols(rest_url, quote, top_n)

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

    def _run_tick_backtest(req, rest_url, quote, start_ts, end_ts,
                          crash_threshold, window_minutes, pump_threshold, pump_window_sec,
                          take_profit, stop_loss, pump_tp, pump_sl,
                          amount, top_n, max_simultaneous_limit, coin_range_start=0,
                          max_duration_hours=0):
        """Tick-by-tick backtest using Binance aggTrades API."""
        from datetime import datetime
        from collections import deque
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time as tm

        scan_start = tm.time()
        window_sec = window_minutes * 60

        symbols = _get_cached_ticker_symbols(rest_url, quote, top_n, offset=coin_range_start)

        def tick_backtest_symbol(symbol):
            trades = []
            try:
                # Step 1: fetch 1-min candles to find volatile periods
                all_candles = []
                cur = start_ts
                for _ in range(15):
                    r = req.get(f"{rest_url}/api/v3/klines", params={
                        "symbol": symbol, "interval": "1m",
                        "startTime": cur, "endTime": end_ts, "limit": 1000
                    }, timeout=15)
                    chunk = r.json()
                    if not chunk or not isinstance(chunk, list):
                        break
                    all_candles.extend(chunk)
                    if len(chunk) < 1000:
                        break
                    cur = chunk[-1][0] + 1

                if not all_candles:
                    return trades

                # Step 2: find volatile windows (candles with >2% range = potential events)
                hot_windows = []
                for c in all_candles:
                    h = float(c[2])
                    l = float(c[3])
                    if h > 0 and ((h - l) / h * 100) >= 2.0:
                        ts_start = c[0] - pump_window_sec * 1000
                        ts_end = c[0] + 120000
                        hot_windows.append((ts_start, ts_end))

                # Merge overlapping windows
                if not hot_windows:
                    return trades
                hot_windows.sort()
                merged = [hot_windows[0]]
                for s, e in hot_windows[1:]:
                    if s <= merged[-1][1]:
                        merged[-1] = (merged[-1][0], max(merged[-1][1], e))
                    else:
                        merged.append((s, e))

                # Step 3: fetch ticks only for hot windows
                all_ticks = []
                for ws, we in merged[:50]:
                    r = req.get(f"{rest_url}/api/v3/aggTrades", params={
                        "symbol": symbol, "startTime": int(ws), "endTime": int(we), "limit": 1000
                    }, timeout=10)
                    chunk = r.json()
                    if chunk and isinstance(chunk, list):
                        all_ticks.extend(chunk)

                if not all_ticks:
                    return trades

                all_ticks.sort(key=lambda x: x["T"])

                # Step 4: simulate with tick data
                price_window = deque()
                in_trade = False
                entry_price = 0
                entry_time = 0
                entry_type = "crash"
                cooldown_until = 0

                for tick in all_ticks:
                    ts = tick["T"] / 1000
                    price = float(tick["p"])
                    price_window.append((ts, price))

                    cutoff_crash = ts - window_sec
                    cutoff_pump = ts - pump_window_sec
                    while price_window and price_window[0][0] < min(cutoff_crash, cutoff_pump):
                        price_window.popleft()

                    if in_trade:
                        tp = pump_tp if entry_type == "pump" else take_profit
                        sl = pump_sl if entry_type == "pump" else stop_loss
                        pnl = ((price - entry_price) / entry_price) * 100
                        if pnl >= tp:
                            exit_price = entry_price * (1 + tp / 100)
                            trades.append({
                                "symbol": symbol,
                                "entry_date": datetime.fromtimestamp(entry_time).strftime("%Y-%m-%d %H:%M:%S"),
                                "exit_date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"),
                                "entry_price": entry_price,
                                "exit_price": round(exit_price, 8),
                                "pnl_pct": round(tp, 2),
                                "pnl_usdt": round(amount * tp / 100, 2),
                                "exit_reason": "TP",
                                "entry_type": entry_type
                            })
                            in_trade = False
                            cooldown_until = ts + 300
                        elif pnl <= -sl:
                            exit_price = entry_price * (1 - sl / 100)
                            trades.append({
                                "symbol": symbol,
                                "entry_date": datetime.fromtimestamp(entry_time).strftime("%Y-%m-%d %H:%M:%S"),
                                "exit_date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"),
                                "entry_price": entry_price,
                                "exit_price": round(exit_price, 8),
                                "pnl_pct": round(-sl, 2),
                                "pnl_usdt": round(-amount * sl / 100, 2),
                                "exit_reason": "SL",
                                "entry_type": entry_type
                            })
                            in_trade = False
                            cooldown_until = ts + 300
                        elif max_duration_hours > 0 and (ts - entry_time) >= max_duration_hours * 3600:
                            trades.append({
                                "symbol": symbol,
                                "entry_date": datetime.fromtimestamp(entry_time).strftime("%Y-%m-%d %H:%M:%S"),
                                "exit_date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"),
                                "entry_price": entry_price,
                                "exit_price": round(price, 8),
                                "pnl_pct": round(pnl, 2),
                                "pnl_usdt": round(amount * pnl / 100, 2),
                                "exit_reason": "TIME",
                                "entry_type": entry_type
                            })
                            in_trade = False
                            cooldown_until = ts + 300
                    else:
                        if ts < cooldown_until:
                            continue

                        max_price = 0
                        min_price = float('inf')
                        for t, p in price_window:
                            if t >= cutoff_crash and p > max_price:
                                max_price = p
                            if t >= cutoff_pump and p < min_price:
                                min_price = p

                        if max_price > 0:
                            drop = ((max_price - price) / max_price) * 100
                            if drop >= crash_threshold:
                                in_trade = True
                                entry_price = price
                                entry_time = ts
                                entry_type = "crash"
                                continue

                        if min_price > 0 and min_price < float('inf'):
                            pump_pct = ((price - min_price) / min_price) * 100
                            if pump_pct >= pump_threshold:
                                in_trade = True
                                entry_price = price
                                entry_time = ts
                                entry_type = "pump"

                if in_trade:
                    last_price = float(all_ticks[-1]["p"])
                    pnl_pct = ((last_price - entry_price) / entry_price) * 100
                    trades.append({
                        "symbol": symbol,
                        "entry_date": datetime.fromtimestamp(entry_time).strftime("%Y-%m-%d %H:%M:%S"),
                        "exit_date": datetime.fromtimestamp(all_ticks[-1]["T"] / 1000).strftime("%Y-%m-%d %H:%M:%S"),
                        "entry_price": entry_price,
                        "exit_price": round(last_price, 8),
                        "pnl_pct": round(pnl_pct, 2),
                        "pnl_usdt": round(amount * pnl_pct / 100, 2),
                        "exit_reason": "OPEN",
                        "entry_type": entry_type
                    })
            except Exception as e:
                logger.debug(f"Tick backtest error for {symbol}: {e}")
            return trades

        all_trades = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(tick_backtest_symbol, s): s for s in symbols}
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
                    d1 = _parse_dt(t["entry_date"])
                    d2 = _parse_dt(t["exit_date"])
                    durations.append((d2 - d1).total_seconds() / 3600)
                except Exception:
                    pass
        avg_duration_hours = round(sum(durations) / len(durations), 1) if durations else 0

        wins = [t for t in all_trades if t["pnl_pct"] > 0]
        losses = [t for t in all_trades if t["pnl_pct"] <= 0]
        total_pnl = sum(t["pnl_usdt"] for t in all_trades)
        crash_trades = sum(1 for t in all_trades if t.get("entry_type") != "pump")
        pump_trades = sum(1 for t in all_trades if t.get("entry_type") == "pump")

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
            "avg_duration_hours": avg_duration_hours,
            "crash_trades": crash_trades,
            "pump_trades": pump_trades
        }

        scan_time = round(tm.time() - scan_start, 1)
        return jsonify({
            "summary": summary,
            "trades": all_trades[:200],
            "coins_scanned": len(symbols),
            "scan_time_seconds": scan_time
        })

    def _run_hybrid_backtest(req, rest_url, quote, start_ts, end_ts,
                            crash_threshold, window_minutes, pump_threshold, pump_window_sec,
                            take_profit, stop_loss, pump_tp, pump_sl,
                            amount, top_n, max_simultaneous_limit,
                            max_duration_hours=0):
        """Hybrid backtest: same crash detection as candle mode, but 1-min precision for exits."""
        from datetime import datetime
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time as tm

        scan_start = tm.time()
        interval_map = {5: "5m", 15: "15m", 60: "1h", 240: "4h", 1440: "1d"}
        interval = interval_map.get(window_minutes, "15m")

        symbols = _get_cached_ticker_symbols(rest_url, quote, top_n)

        def fetch_klines(symbol, intv, ts_start, ts_end, max_pages=15):
            all_k = []
            cur = ts_start
            for _ in range(max_pages):
                r = req.get(f"{rest_url}/api/v3/klines", params={
                    "symbol": symbol, "interval": intv,
                    "startTime": cur, "endTime": ts_end, "limit": 1000
                }, timeout=15)
                chunk = r.json()
                if not chunk or not isinstance(chunk, list):
                    break
                all_k.extend(chunk)
                if len(chunk) < 1000:
                    break
                cur = chunk[-1][0] + 1
            return all_k

        def hybrid_backtest_symbol(symbol):
            trades = []
            try:
                klines = fetch_klines(symbol, interval, start_ts, end_ts)
                if not klines:
                    return trades

                signal_candles = []
                for i in range(len(klines)):
                    high = float(klines[i][2])
                    low = float(klines[i][3])
                    opn = float(klines[i][1])
                    close = float(klines[i][4])
                    if high == 0 or low == 0:
                        continue
                    drop = ((high - low) / high) * 100
                    if drop >= crash_threshold:
                        signal_candles.append({
                            "ts": int(klines[i][0]),
                            "high": high,
                            "low": low,
                            "entry_price": low,
                            "entry_type": "crash"
                        })
                    if pump_threshold < 99999 and opn > 0:
                        pump_pct = ((close - opn) / opn) * 100
                        if pump_pct >= pump_threshold and close > opn:
                            signal_candles.append({
                                "ts": int(klines[i][0]),
                                "high": high,
                                "low": low,
                                "entry_price": opn,
                                "entry_type": "pump"
                            })
                signal_candles.sort(key=lambda x: x["ts"])

                if not signal_candles:
                    return trades

                in_trade = False
                entry_price = 0
                entry_time = 0
                entry_type = "crash"
                sig_idx = 0

                while sig_idx < len(signal_candles):
                    cc = signal_candles[sig_idx]
                    sig_idx += 1

                    if in_trade:
                        continue

                    entry_price = cc["entry_price"]
                    entry_time = cc["ts"] / 1000
                    entry_type = cc["entry_type"]
                    entry_date = datetime.fromtimestamp(entry_time).strftime("%Y-%m-%d %H:%M:%S")
                    in_trade = True

                    tp = pump_tp if entry_type == "pump" else take_profit
                    sl = pump_sl if entry_type == "pump" else stop_loss

                    max_dur_ms = int(max_duration_hours * 3600 * 1000) if max_duration_hours > 0 else 86400000
                    exit_search_end = cc["ts"] + max_dur_ms + 3600000

                    exit_candles = fetch_klines(symbol, "1m", cc["ts"], min(exit_search_end, end_ts), max_pages=30)

                    trade_closed = False
                    for ec in exit_candles:
                        ets = ec[0] / 1000
                        ehigh = float(ec[2])
                        elow = float(ec[3])
                        eclose = float(ec[4])
                        edate = datetime.fromtimestamp(ets).strftime("%Y-%m-%d %H:%M:%S")

                        pnl_high = ((ehigh - entry_price) / entry_price) * 100
                        pnl_low = ((elow - entry_price) / entry_price) * 100

                        if pnl_high >= tp:
                            exit_price = entry_price * (1 + tp / 100)
                            trades.append({
                                "symbol": symbol,
                                "entry_date": entry_date,
                                "exit_date": edate,
                                "entry_price": entry_price,
                                "exit_price": round(exit_price, 8),
                                "pnl_pct": round(tp, 2),
                                "pnl_usdt": round(amount * tp / 100, 2),
                                "exit_reason": "TP",
                                "entry_type": entry_type
                            })
                            trade_closed = True
                            break
                        elif pnl_low <= -sl:
                            exit_price = entry_price * (1 - sl / 100)
                            trades.append({
                                "symbol": symbol,
                                "entry_date": entry_date,
                                "exit_date": edate,
                                "entry_price": entry_price,
                                "exit_price": round(exit_price, 8),
                                "pnl_pct": round(-sl, 2),
                                "pnl_usdt": round(-amount * sl / 100, 2),
                                "exit_reason": "SL",
                                "entry_type": entry_type
                            })
                            trade_closed = True
                            break
                        elif max_duration_hours > 0 and (ets - entry_time) >= max_duration_hours * 3600:
                            pnl = ((eclose - entry_price) / entry_price) * 100
                            trades.append({
                                "symbol": symbol,
                                "entry_date": entry_date,
                                "exit_date": edate,
                                "entry_price": entry_price,
                                "exit_price": round(eclose, 8),
                                "pnl_pct": round(pnl, 2),
                                "pnl_usdt": round(amount * pnl / 100, 2),
                                "exit_reason": "TIME",
                                "entry_type": entry_type
                            })
                            trade_closed = True
                            break

                    if not trade_closed:
                        if exit_candles:
                            last = exit_candles[-1]
                            last_close = float(last[4])
                            last_ts = last[0] / 1000
                            pnl = ((last_close - entry_price) / entry_price) * 100
                            trades.append({
                                "symbol": symbol,
                                "entry_date": entry_date,
                                "exit_date": datetime.fromtimestamp(last_ts).strftime("%Y-%m-%d %H:%M:%S"),
                                "entry_price": entry_price,
                                "exit_price": round(last_close, 8),
                                "pnl_pct": round(pnl, 2),
                                "pnl_usdt": round(amount * pnl / 100, 2),
                                "exit_reason": "OPEN",
                                "entry_type": entry_type
                            })

                    in_trade = False
                    if trade_closed and sig_idx < len(signal_candles):
                        exit_ts = trades[-1]["exit_date"] if trades else ""
                        while sig_idx < len(signal_candles):
                            next_crash_date = datetime.fromtimestamp(signal_candles[sig_idx]["ts"] / 1000).strftime("%Y-%m-%d %H:%M:%S")
                            if next_crash_date > exit_ts:
                                break
                            sig_idx += 1

            except Exception as e:
                logger.debug(f"Hybrid backtest error for {symbol}: {e}")
            return trades

        all_trades = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(hybrid_backtest_symbol, s): s for s in symbols}
            for future in as_completed(futures):
                all_trades.extend(future.result())

        all_trades.sort(key=lambda x: x["entry_date"])

        if max_simultaneous_limit > 0 and all_trades:
            filtered = []
            open_t = []
            skipped = 0
            for t in all_trades:
                open_t = [ot for ot in open_t if ot["exit_date"] > t["entry_date"]]
                if len(open_t) >= max_simultaneous_limit:
                    skipped += 1
                    continue
                filtered.append(t)
                open_t.append(t)
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
                    d1 = _parse_dt(t["entry_date"])
                    d2 = _parse_dt(t["exit_date"])
                    durations.append((d2 - d1).total_seconds() / 3600)
                except Exception:
                    pass
        avg_duration_hours = round(sum(durations) / len(durations), 1) if durations else 0

        wins = [t for t in all_trades if t["pnl_pct"] > 0]
        losses = [t for t in all_trades if t["pnl_pct"] <= 0]
        total_pnl = sum(t["pnl_usdt"] for t in all_trades)
        crash_trades = sum(1 for t in all_trades if t.get("entry_type") != "pump")
        pump_trades = sum(1 for t in all_trades if t.get("entry_type") == "pump")

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
            "avg_duration_hours": avg_duration_hours,
            "crash_trades": crash_trades,
            "pump_trades": pump_trades
        }

        scan_time = round(tm.time() - scan_start, 1)
        return jsonify({
            "summary": summary,
            "trades": all_trades[:200],
            "coins_scanned": len(symbols),
            "scan_time_seconds": scan_time
        })

    @app.route("/api/backtest/refine", methods=["POST"])
    def backtest_refine():
        """Refine backtest trades with tick-by-tick data from Binance aggTrades."""
        import requests as req
        from datetime import datetime
        from collections import deque
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time as tm

        try:
            data = request.get_json()
            input_trades = data.get("trades", [])
            take_profit = float(data.get("take_profit", 50))
            stop_loss = float(data.get("stop_loss", 20))
            pump_tp = float(data.get("pump_tp", take_profit))
            pump_sl = float(data.get("pump_sl", stop_loss))
            amount = float(data.get("amount", 1000))
            max_duration_hours = float(data.get("max_duration_hours", 0))
            max_simultaneous_limit = int(data.get("max_simultaneous", 10))
            window_minutes = int(data.get("window_minutes", 60))
            crash_threshold = float(data.get("threshold", 30))
            pump_threshold = float(data.get("pump_threshold", 5))
            pump_window_sec = int(data.get("pump_window_seconds", 5))
            window_sec = window_minutes * 60

            rest_url = config.get("binance", {}).get("rest_url", "https://api.binance.com")
            scan_start = tm.time()

            trade_entries = []
            for t in input_trades:
                trade_entries.append({
                    "symbol": t["symbol"],
                    "entry_date": t["entry_date"],
                    "entry_price": t["entry_price"],
                    "entry_type": t.get("entry_type", "crash"),
                    "entry_ts": int(_parse_dt(t["entry_date"]).timestamp() * 1000)
                })

            def refine_trade(te):
                try:
                    symbol = te["symbol"]
                    entry_ts = te["entry_ts"]
                    entry_type = te["entry_type"]
                    tp = pump_tp if entry_type == "pump" else take_profit
                    sl = pump_sl if entry_type == "pump" else stop_loss

                    tick_start = entry_ts - window_sec * 1000
                    max_dur_ms = int(max_duration_hours * 3600 * 1000) if max_duration_hours > 0 else 86400000
                    tick_end = entry_ts + max_dur_ms + 3600000

                    price_window = deque()
                    in_trade = False
                    entry_price = 0
                    entry_time = 0
                    last_tick = None
                    got_any = False

                    cur_ts = tick_start
                    trade_deadline = tm.time() + 60
                    for _ in range(50):
                        if tm.time() > trade_deadline:
                            break
                        r = req.get(f"{rest_url}/api/v3/aggTrades", params={
                            "symbol": symbol, "startTime": cur_ts, "endTime": tick_end, "limit": 1000
                        }, timeout=10)
                        chunk = r.json()
                        if not chunk or not isinstance(chunk, list):
                            break
                        got_any = True
                        chunk.sort(key=lambda x: x["T"])
                        for tick in chunk:
                            last_tick = tick
                            ts = tick["T"] / 1000
                            price = float(tick["p"])
                            price_window.append((ts, price))
                            cutoff = ts - window_sec
                            while price_window and price_window[0][0] < cutoff:
                                price_window.popleft()
                            if in_trade:
                                break
                            else:
                                if tick["T"] < entry_ts:
                                    continue
                                if entry_type == "pump":
                                    cutoff_pump = ts - pump_window_sec
                                    min_price = min((p for t2, p in price_window if t2 >= cutoff_pump), default=float('inf'))
                                    if min_price > 0 and min_price < float('inf'):
                                        pump_pct = ((price - min_price) / min_price) * 100
                                        if pump_pct >= pump_threshold:
                                            in_trade = True
                                            entry_price = price
                                            entry_time = ts
                                else:
                                    max_price = max((p for t2, p in price_window if t2 >= cutoff), default=0)
                                    if max_price > 0:
                                        drop = ((max_price - price) / max_price) * 100
                                        if drop >= crash_threshold:
                                            in_trade = True
                                            entry_price = price
                                            entry_time = ts
                        if in_trade:
                            break
                        if len(chunk) < 1000:
                            break
                        cur_ts = chunk[-1]["T"] + 1
                        tm.sleep(0.05)
                    if in_trade and entry_price > 0:
                        kline_start = int(entry_time * 1000)
                        kline_end_ts = kline_start + max_dur_ms + 3600000
                        kl_url = f"{rest_url}/api/v3/klines"
                        kl_all = []
                        kl_cur = kline_start
                        for _ in range(20):
                            kr = req.get(kl_url, params={"symbol": symbol, "interval": "1m", "startTime": kl_cur, "endTime": kline_end_ts, "limit": 1000}, timeout=10)
                            kd = kr.json()
                            if not kd or not isinstance(kd, list):
                                break
                            kl_all.extend(kd)
                            if len(kd) < 1000:
                                break
                            kl_cur = kd[-1][0] + 1
                            tm.sleep(0.05)
                        for kl in kl_all:
                            kl_ts = kl[0] / 1000
                            kl_high = float(kl[2])
                            kl_low = float(kl[3])
                            kl_close = float(kl[4])
                            pnl_high = ((kl_high - entry_price) / entry_price) * 100
                            pnl_low = ((kl_low - entry_price) / entry_price) * 100
                            if pnl_high >= tp:
                                exit_price = entry_price * (1 + tp / 100)
                                return {"symbol": symbol, "entry_date": datetime.fromtimestamp(entry_time).strftime("%Y-%m-%d %H:%M:%S"), "exit_date": datetime.fromtimestamp(kl_ts).strftime("%Y-%m-%d %H:%M:%S"), "entry_price": entry_price, "exit_price": round(exit_price, 8), "pnl_pct": round(tp, 2), "pnl_usdt": round(amount * tp / 100, 2), "exit_reason": "TP", "entry_type": entry_type}
                            if pnl_low <= -sl:
                                exit_price = entry_price * (1 - sl / 100)
                                return {"symbol": symbol, "entry_date": datetime.fromtimestamp(entry_time).strftime("%Y-%m-%d %H:%M:%S"), "exit_date": datetime.fromtimestamp(kl_ts).strftime("%Y-%m-%d %H:%M:%S"), "entry_price": entry_price, "exit_price": round(exit_price, 8), "pnl_pct": round(-sl, 2), "pnl_usdt": round(-amount * sl / 100, 2), "exit_reason": "SL", "entry_type": entry_type}
                            if max_duration_hours > 0 and (kl_ts - entry_time) >= max_duration_hours * 3600:
                                pnl = ((kl_close - entry_price) / entry_price) * 100
                                return {"symbol": symbol, "entry_date": datetime.fromtimestamp(entry_time).strftime("%Y-%m-%d %H:%M:%S"), "exit_date": datetime.fromtimestamp(kl_ts).strftime("%Y-%m-%d %H:%M:%S"), "entry_price": entry_price, "exit_price": round(kl_close, 8), "pnl_pct": round(pnl, 2), "pnl_usdt": round(amount * pnl / 100, 2), "exit_reason": "TIME", "entry_type": entry_type}
                        if kl_all:
                            last_kl = kl_all[-1]
                            last_close = float(last_kl[4])
                            last_ts = last_kl[0] / 1000
                            pnl = ((last_close - entry_price) / entry_price) * 100
                            return {"symbol": symbol, "entry_date": datetime.fromtimestamp(entry_time).strftime("%Y-%m-%d %H:%M:%S"), "exit_date": datetime.fromtimestamp(last_ts).strftime("%Y-%m-%d %H:%M:%S"), "entry_price": entry_price, "exit_price": round(last_close, 8), "pnl_pct": round(pnl, 2), "pnl_usdt": round(amount * pnl / 100, 2), "exit_reason": "OPEN", "entry_type": entry_type}

                    if not got_any:
                        return te

                    if in_trade and last_tick:
                        last_price = float(last_tick["p"])
                        last_ts = last_tick["T"] / 1000
                        pnl = ((last_price - entry_price) / entry_price) * 100
                        return {
                            "symbol": symbol,
                            "entry_date": datetime.fromtimestamp(entry_time).strftime("%Y-%m-%d %H:%M:%S"),
                            "exit_date": datetime.fromtimestamp(last_ts).strftime("%Y-%m-%d %H:%M:%S"),
                            "entry_price": entry_price,
                            "exit_price": round(last_price, 8),
                            "pnl_pct": round(pnl, 2),
                            "pnl_usdt": round(amount * pnl / 100, 2),
                            "exit_reason": "OPEN",
                            "entry_type": entry_type
                        }
                    return None
                except Exception as e:
                    logger.debug(f"Refine error for {te['symbol']}: {e}")
                    return None
            all_trades = []
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(refine_trade, te): te for te in trade_entries}
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        all_trades.append(result)

            all_trades.sort(key=lambda x: x["entry_date"])

            if max_simultaneous_limit > 0 and all_trades:
                filtered = []
                open_t = []
                skipped = 0
                for t in all_trades:
                    open_t = [ot for ot in open_t if ot["exit_date"] > t["entry_date"]]
                    if len(open_t) >= max_simultaneous_limit:
                        skipped += 1
                        continue
                    filtered.append(t)
                    open_t.append(t)
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
                        d1 = _parse_dt(t["entry_date"])
                        d2 = _parse_dt(t["exit_date"])
                        durations.append((d2 - d1).total_seconds() / 3600)
                    except Exception:
                        pass
            avg_duration_hours = round(sum(durations) / len(durations), 1) if durations else 0

            wins = [t for t in all_trades if t["pnl_pct"] > 0]
            losses = [t for t in all_trades if t["pnl_pct"] <= 0]
            total_pnl = sum(t["pnl_usdt"] for t in all_trades)
            crash_trades = sum(1 for t in all_trades if t.get("entry_type") != "pump")
            pump_trades = sum(1 for t in all_trades if t.get("entry_type") == "pump")

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
                "avg_duration_hours": avg_duration_hours,
                "crash_trades": crash_trades,
                "pump_trades": pump_trades
            }

            scan_time = round(tm.time() - scan_start, 1)
            return jsonify({
                "summary": summary,
                "trades": all_trades[:200],
                "scan_time_seconds": scan_time
            })

        except Exception as e:
            logger.error(f"Refine error: {e}")
            return jsonify({"error": str(e)})

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
            bt_mode = data.get("mode", "candle")
            _pump_raw = data.get("pump_enabled", False)
            pump_only_mode = (_pump_raw == "pump_only")
            pump_enabled = (_pump_raw == "on" or _pump_raw is True or pump_only_mode)
            pump_threshold = float(data.get("pump_threshold", 5)) if pump_enabled else 99999
            if pump_only_mode:
                threshold = 99999
            pump_window_sec = int(data.get("pump_window_seconds", 5))
            pump_tp = float(data.get("pump_tp", take_profit))
            pump_sl = float(data.get("pump_sl", stop_loss))
            coin_range_start = int(data.get("coin_range_start", 0))
            max_duration_hours = float(data.get("max_duration_hours", 0))

            start_ts = int(datetime.strptime(date_from, "%Y-%m-%d").timestamp() * 1000)
            end_ts = int(datetime.strptime(date_to + " 23:59:59", "%Y-%m-%d %H:%M:%S").timestamp() * 1000)

            rest_url = config.get("binance", {}).get("rest_url", "https://api.binance.com")
            quote = config.get("binance", {}).get("quote_asset", "USDT")

            if bt_mode == "tick":
                top_n = min(top_n, 20)
                return _run_tick_backtest(
                    req, rest_url, quote, start_ts, end_ts,
                    threshold, window_minutes, pump_threshold, pump_window_sec,
                    take_profit, stop_loss, pump_tp, pump_sl,
                    amount, top_n, max_simultaneous_limit, coin_range_start,
                    max_duration_hours
                )

            if bt_mode == "hybrid":
                return _run_hybrid_backtest(
                    req, rest_url, quote, start_ts, end_ts,
                    threshold, window_minutes, pump_threshold, pump_window_sec,
                    take_profit, stop_loss, pump_tp, pump_sl,
                    amount, top_n, max_simultaneous_limit,
                    max_duration_hours
                )

            interval_map = {5: "5m", 15: "15m", 60: "1h", 240: "4h", 1440: "1d"}
            interval = interval_map.get(window_minutes, "15m")

            scan_start = time.time()

            symbols = _get_cached_ticker_symbols(rest_url, quote, top_n)

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
                    entry_ts = 0
                    entry_type = "crash"

                    for i in range(len(klines)):
                        high = float(klines[i][2])
                        low = float(klines[i][3])
                        close = float(klines[i][4])
                        candle_ts = int(klines[i][0]) / 1000

                        if in_trade:
                            tp = pump_tp if entry_type == "pump" else take_profit
                            sl = pump_sl if entry_type == "pump" else stop_loss
                            pnl_high = ((high - entry_price) / entry_price) * 100
                            pnl_low = ((low - entry_price) / entry_price) * 100
                            pnl_close = ((close - entry_price) / entry_price) * 100
                            candle_date = datetime.fromtimestamp(candle_ts).strftime("%Y-%m-%d %H:%M")

                            if pnl_high >= tp:
                                exit_price = entry_price * (1 + tp / 100)
                                pnl_usdt = amount * tp / 100
                                trades.append({
                                    "symbol": symbol,
                                    "entry_date": entry_date,
                                    "exit_date": candle_date,
                                    "entry_price": entry_price,
                                    "exit_price": round(exit_price, 8),
                                    "pnl_pct": round(tp, 2),
                                    "pnl_usdt": round(pnl_usdt, 2),
                                    "exit_reason": "TP",
                                    "entry_type": entry_type
                                })
                                in_trade = False
                            elif pnl_low <= -sl:
                                exit_price = entry_price * (1 - sl / 100)
                                pnl_usdt = -amount * sl / 100
                                trades.append({
                                    "symbol": symbol,
                                    "entry_date": entry_date,
                                    "exit_date": candle_date,
                                    "entry_price": entry_price,
                                    "exit_price": round(exit_price, 8),
                                    "pnl_pct": round(-sl, 2),
                                    "pnl_usdt": round(pnl_usdt, 2),
                                    "exit_reason": "SL",
                                    "entry_type": entry_type
                                })
                                in_trade = False
                            elif max_duration_hours > 0 and (candle_ts - entry_ts) >= max_duration_hours * 3600:
                                pnl_usdt = amount * pnl_close / 100
                                trades.append({
                                    "symbol": symbol,
                                    "entry_date": entry_date,
                                    "exit_date": candle_date,
                                    "entry_price": entry_price,
                                    "exit_price": round(close, 8),
                                    "pnl_pct": round(pnl_close, 2),
                                    "pnl_usdt": round(pnl_usdt, 2),
                                    "exit_reason": "TIME",
                                    "entry_type": entry_type
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
                                entry_ts = candle_ts
                                entry_type = "crash"
                                entry_date = datetime.fromtimestamp(candle_ts).strftime("%Y-%m-%d %H:%M")

                            if not in_trade and pump_enabled and low > 0:
                                opn = float(klines[i][1])
                                if opn > 0:
                                    pump_pct = ((close - opn) / opn) * 100
                                    if pump_pct >= pump_threshold and close > opn:
                                        in_trade = True
                                        entry_price = opn
                                        entry_ts = candle_ts
                                        entry_type = "pump"
                                        entry_date = datetime.fromtimestamp(candle_ts).strftime("%Y-%m-%d %H:%M")

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
                            "exit_reason": "OPEN",
                            "entry_type": entry_type
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
                        d1 = _parse_dt(t["entry_date"])
                        d2 = _parse_dt(t["exit_date"])
                        durations.append((d2 - d1).total_seconds() / 3600)
                    except Exception:
                        pass
            avg_duration_hours = round(sum(durations) / len(durations), 1) if durations else 0

            wins = [t for t in all_trades if t["pnl_pct"] > 0]
            losses = [t for t in all_trades if t["pnl_pct"] <= 0]
            total_pnl = sum(t["pnl_usdt"] for t in all_trades)
            crash_trades = sum(1 for t in all_trades if t.get("entry_type") != "pump")
            pump_trades = sum(1 for t in all_trades if t.get("entry_type") == "pump")

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
                "avg_duration_hours": avg_duration_hours,
                "crash_trades": crash_trades,
                "pump_trades": pump_trades
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

            if "max_simultaneous_trades" in data:
                val = int(data["max_simultaneous_trades"])
                trading_cfg["max_simultaneous_trades"] = val
                if detector_ref:
                    detector_ref[0].max_simultaneous_trades = val

            if "max_duration_hours" in data:
                val = float(data["max_duration_hours"])
                trading_cfg["max_duration_hours"] = val
                if detector_ref:
                    detector_ref[0].max_duration_hours = val

            if "trading_pairs_limit" in data:
                val = int(data["trading_pairs_limit"])
                config["binance"]["top_pairs_count"] = val
                if detector_ref:
                    detector_ref[0].trading_pairs_limit = val
                    if len(detector_ref) > 1:
                        monitor = detector_ref[1]
                        detector_ref[0].update_allowed_symbols(monitor.symbols)

            if "pump_mode" in data:
                mode = data["pump_mode"]
                if mode == "pump_only":
                    detection_cfg["pump_detection"] = True
                    detection_cfg["pump_only"] = True
                    detection_cfg["drop_threshold_percent"] = 99999
                    if detector_ref:
                        detector_ref[0].pump_detection = True
                        detector_ref[0].pump_only = True
                        detector_ref[0].drop_threshold = 99999
                elif mode == "on":
                    detection_cfg["pump_detection"] = True
                    detection_cfg["pump_only"] = False
                    if detector_ref:
                        detector_ref[0].pump_detection = True
                        detector_ref[0].pump_only = False
                else:
                    detection_cfg["pump_detection"] = False
                    detection_cfg["pump_only"] = False
                    if detector_ref:
                        detector_ref[0].pump_detection = False
                        detector_ref[0].pump_only = False
            elif "pump_detection" in data:
                val = bool(data["pump_detection"])
                detection_cfg["pump_detection"] = val
                if detector_ref:
                    detector_ref[0].pump_detection = val

            if "pump_tp" in data:
                val = float(data["pump_tp"])
                trading_cfg["pump_tp_percent"] = val
                if detector_ref:
                    detector_ref[0].pump_tp = val

            if "pump_sl" in data:
                val = float(data["pump_sl"])
                trading_cfg["pump_sl_percent"] = val
                if detector_ref:
                    detector_ref[0].pump_sl = val

            if "pump_threshold_percent" in data:
                val = float(data["pump_threshold_percent"])
                detection_cfg["pump_threshold_percent"] = val
                if detector_ref:
                    detector_ref[0].pump_threshold = val

            if "pump_window_seconds" in data:
                val = int(data["pump_window_seconds"])
                detection_cfg["pump_window_seconds"] = val
                if detector_ref:
                    detector_ref[0].pump_window_sec = val

            # Save to config.json
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    full_config = json.load(f)
                full_config["binance"] = config.get("binance", full_config.get("binance", {}))
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


    @app.route("/api/close-position/<int:trade_id>", methods=["POST"])
    def api_close_position(trade_id):
        trade = database.get_trade(trade_id)
        if not trade:
            return jsonify({"success": False, "error": "Trade not found"})
        if trade["status"] != "OPEN":
            return jsonify({"success": False, "error": "Trade already closed"})

        symbol = trade["symbol"]
        quantity = trade["quantity"]

        _trader = detector_ref[0].trader if detector_ref else None
        if _trader and _trader.live_mode:
            result = _trader.market_sell(symbol, quantity)
            if result:
                close_price = result["avg_price"]
                logger.info(f"LIVE CLOSE: {symbol} #{trade_id} sold -> {result['filled_quote']:.2f} USDC")
            else:
                close_price = trade.get("current_price") or trade["entry_price"]
                logger.warning(f"LIVE CLOSE FALLBACK: {symbol} #{trade_id} Binance sell failed, closing in DB at {close_price}")
        else:
            close_price = trade.get("current_price") or trade["entry_price"]
            logger.info(f"DEMO CLOSE: {symbol} #{trade_id} at {close_price}")

        database.close_trade(trade_id, close_price)
        return jsonify({"success": True, "close_price": close_price})

    @app.route("/api/close-all", methods=["POST"])
    def api_close_all():
        open_trades = database.get_open_trades()
        closed = 0
        failed = 0
        _results = []
        _total_invested = 0
        _total_received = 0
        for t in open_trades:
            try:
                _trader = detector_ref[0].trader if detector_ref else None
                _entry = t["entry_price"]
                _qty = t["quantity"]
                _invested = _entry * _qty
                if _trader and _trader.live_mode:
                    result = _trader.market_sell(t["symbol"], t["quantity"])
                    if result:
                        cp = result["avg_price"]
                        _received = float(result.get("filled_quote", cp * _qty))
                        logger.info(f"CLOSE ALL LIVE: {t['symbol']} #{t['id']} sold -> {_received:.2f} USDC")
                    else:
                        cp = t.get("current_price") or _entry
                        _received = cp * _qty
                        logger.warning(f"CLOSE ALL FALLBACK: {t['symbol']} #{t['id']} Binance sell failed, DB close at {cp}")
                else:
                    cp = t.get("current_price") or _entry
                    _received = cp * _qty
                    logger.info(f"CLOSE ALL DEMO: {t['symbol']} #{t['id']} at {cp}")
                database.close_trade(t["id"], cp)
                _pnl = _received - _invested
                _total_invested += _invested
                _total_received += _received
                _results.append({"symbol": t["symbol"], "entry": round(_entry, 8), "close": round(cp, 8), "qty": round(_qty, 8), "invested": round(_invested, 4), "received": round(_received, 4), "pnl": round(_pnl, 4)})
                closed += 1
            except Exception as ex:
                logger.error(f"CLOSE ALL ERROR: {t['symbol']} #{t['id']} - {ex}")
                failed += 1
        _total_pnl = round(_total_received - _total_invested, 4)
        _wins = sum(1 for r in _results if r["pnl"] > 0)
        _losses = sum(1 for r in _results if r["pnl"] <= 0)
        _best = max(_results, key=lambda x: x["pnl"]) if _results else None
        _worst = min(_results, key=lambda x: x["pnl"]) if _results else None
        return jsonify({"success": True, "closed": closed, "failed": failed, "total_pnl": _total_pnl, "total_invested": round(_total_invested, 2), "total_received": round(_total_received, 2), "wins": _wins, "losses": _losses, "best": _best, "worst": _worst, "trades": _results})

    return app
