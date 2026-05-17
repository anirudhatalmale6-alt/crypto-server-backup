import json
import os
import sys
import time
import logging
import threading

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("multi_strategy.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


def load_config(path="config.json"):
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    with open(config_path, "r") as f:
        return json.load(f)


def main():
    logger.info("=== MULTI-STRATEGY DASHBOARD v1.0 ===")
    config = load_config()

    from database import MultiStrategyDatabase
    from strategy import StrategyManager
    from monitor import run_monitor
    from dashboard import create_app

    db_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        config.get("database", {}).get("path", "multi_strategy.db")
    )
    db = MultiStrategyDatabase(db_path)

    manager = StrategyManager(db)
    strategies_cfg = config.get("strategies", {})
    for sid, scfg in strategies_cfg.items():
        manager.register(sid, scfg)
        logger.info(f"Registered strategy {sid}: TP={scfg.get('tp_percent')}% SL={scfg.get('sl_percent')}% Amount={scfg.get('trade_amount')} Active={scfg.get('active')}")

    detector_ref = []

    monitor_thread = threading.Thread(
        target=run_monitor,
        args=(config, manager, detector_ref),
        daemon=True,
        name="MultiMonitor"
    )
    monitor_thread.start()
    logger.info("Monitor thread started")
    time.sleep(2)

    dashboard_cfg = config.get("dashboard", {})
    host = dashboard_cfg.get("host", "0.0.0.0")
    port = dashboard_cfg.get("port", 1111)

    app = create_app(config, db, manager, detector_ref)
    logger.info(f"Dashboard starting at http://{host}:{port}")

    try:
        app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    main()
