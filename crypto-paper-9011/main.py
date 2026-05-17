"""
main.py - Entry point for the Crypto Crash Detector.

Starts the Binance WebSocket monitor in a background thread
and the Flask dashboard in the main thread.
"""

import json
import os
import sys
import time
import logging
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("crash_detector.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


def load_config(path="config.json") -> dict:
    """Load configuration from JSON file."""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found: {config_path}")
        logger.info("Please copy config.json.example to config.json and update settings.")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    logger.info("Configuration loaded successfully")
    return config


def print_banner():
    """Print startup banner."""
    banner = """
    ============================================================
                    CRYPTO CRASH DETECTOR v1.0
    ============================================================
      Monitors top 500 Binance USDT pairs for flash crashes
      Threshold: configurable (default 30%+ drop)
      Paper trading with simulated P&L tracking
    ============================================================
    """
    print(banner)


def main():
    """Main entry point."""
    print_banner()

    # Load configuration
    config = load_config()

    # Display settings
    detection = config.get("detection", {})
    trading = config.get("trading", {})
    alerts_cfg = config.get("alerts", {})
    dashboard_cfg = config.get("dashboard", {})

    logger.info(f"Drop threshold: {detection.get('drop_threshold_percent', 30)}%")
    logger.info(f"Time windows: {detection.get('time_windows_minutes', [7, 15])} minutes")
    logger.info(f"Trade amount: EUR {trading.get('amount_per_trade_eur', 1000)}")
    logger.info(f"Take profit: {trading.get('take_profit_percent', 50)}%")
    logger.info(f"Stop loss: {trading.get('stop_loss_percent', 20)}%")
    trade_mode = trading.get("mode", "demo").upper()
    logger.info(f"Trading mode: {trade_mode}")
    if trade_mode == "LIVE":
        logger.warning("*** LIVE TRADING ENABLED - Real orders will be placed on Binance! ***")
    logger.info(f"Sound alerts: {'ON' if alerts_cfg.get('sound_enabled') else 'OFF'}")
    logger.info(f"Telegram: {'ON' if alerts_cfg.get('telegram_enabled') else 'OFF'}")

    # Initialize components
    from database import Database
    from alerts import AlertManager
    from monitor import run_monitor
    from dashboard import create_app

    db_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        config.get("database", {}).get("path", "crash_detector.db")
    )
    database = Database(db_path)
    alert_manager = AlertManager(config)

    # Shared reference for detector (monitor thread -> dashboard)
    detector_ref = []

    # Start monitor in background thread
    monitor_thread = threading.Thread(
        target=run_monitor,
        args=(config, database, alert_manager, detector_ref),
        daemon=True,
        name="BinanceMonitor"
    )
    monitor_thread.start()
    logger.info("Monitor thread started")

    # Wait briefly for monitor to initialize
    time.sleep(2)

    # Create and start Flask dashboard
    host = dashboard_cfg.get("host", "127.0.0.1")
    port = dashboard_cfg.get("port", 5000)

    logger.info(f"Starting dashboard at http://{host}:{port}")
    print(f"\n  >> Dashboard: http://{host}:{port}")
    print(f"  >> Press Ctrl+C to stop\n")

    app = create_app(config, database, detector_ref)

    try:
        app.run(
            host=host,
            port=port,
            debug=False,
            use_reloader=False,
            threaded=True
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        if len(detector_ref) >= 2:
            detector_ref[1].stop()
        logger.info("Goodbye!")


if __name__ == "__main__":
    main()
