"""
alerts.py - Sound alerts and Telegram notifications for crash events.
"""

import sys
import threading
import time
import logging
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)


class SoundAlert:
    """Cross-platform sound alert handler (Windows preferred)."""

    def __init__(self, enabled=True, repeat=3):
        self.enabled = enabled
        self.repeat = repeat
        self._is_windows = sys.platform == "win32"

    def play_alert(self):
        """Play alert sound. Uses winsound on Windows, fallback on other OS."""
        if not self.enabled:
            return

        def _play():
            try:
                if self._is_windows:
                    import winsound
                    for i in range(self.repeat):
                        # High-pitched urgent beep
                        winsound.Beep(1000, 500)
                        time.sleep(0.1)
                        winsound.Beep(1500, 300)
                        time.sleep(0.1)
                        winsound.Beep(2000, 500)
                        if i < self.repeat - 1:
                            time.sleep(0.5)
                else:
                    # Fallback: print bell character
                    for _ in range(self.repeat):
                        print("\a", end="", flush=True)
                        time.sleep(0.5)
            except Exception as e:
                logger.warning(f"Sound alert failed: {e}")

        # Run in thread to not block main loop
        t = threading.Thread(target=_play, daemon=True)
        t.start()


class TelegramAlert:
    """Telegram bot notification sender."""

    def __init__(self, bot_token: str, chat_id: str, enabled: bool = True):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled
        self._session = None

    async def send_crash_alert(self, symbol: str, drop_percent: float,
                               price_start: float, price_end: float,
                               time_window_min: int):
        """Send a crash detection alert via Telegram."""
        if not self.enabled:
            return
        if self.bot_token == "YOUR_BOT_TOKEN_HERE":
            logger.debug("Telegram not configured, skipping notification")
            return

        message = (
            f"🚨 *CRASH DETECTED* 🚨\n\n"
            f"*Pair:* `{symbol}`\n"
            f"*Drop:* {drop_percent:.1f}%\n"
            f"*Price:* {price_start:.8g} → {price_end:.8g}\n"
            f"*Window:* {time_window_min} minutes\n"
            f"*Time:* {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"💰 Simulated BUY order placed at {price_end:.8g}"
        )

        await self._send_message(message)

    async def send_trade_update(self, symbol: str, pnl_percent: float,
                                pnl_eur: float, status: str):
        """Send trade status update."""
        if not self.enabled:
            return
        if self.bot_token == "YOUR_BOT_TOKEN_HERE":
            return

        emoji = "✅" if pnl_eur >= 0 else "❌"
        message = (
            f"{emoji} *Trade {status}*\n\n"
            f"*Pair:* `{symbol}`\n"
            f"*P&L:* {pnl_percent:+.2f}% ({pnl_eur:+.2f} EUR)\n"
            f"*Time:* {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        await self._send_message(message)

    async def send_status(self, message: str):
        """Send a general status message."""
        if not self.enabled:
            return
        if self.bot_token == "YOUR_BOT_TOKEN_HERE":
            return
        await self._send_message(message)

    async def _send_message(self, text: str):
        """Send message via Telegram Bot API using aiohttp."""
        try:
            import aiohttp
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.error(f"Telegram API error {resp.status}: {body}")
                    else:
                        logger.debug(f"Telegram message sent to {self.chat_id}")
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")


class AlertManager:
    """Coordinates all alert channels."""

    def __init__(self, config: dict):
        alerts_cfg = config.get("alerts", {})

        self.sound = SoundAlert(
            enabled=alerts_cfg.get("sound_enabled", True),
            repeat=alerts_cfg.get("sound_repeat", 3)
        )

        self.telegram = TelegramAlert(
            bot_token=alerts_cfg.get("telegram_bot_token", ""),
            chat_id=alerts_cfg.get("telegram_chat_id", ""),
            enabled=alerts_cfg.get("telegram_enabled", False)
        )

        # Cooldown: don't spam alerts for same symbol within 60 seconds
        self._last_alert_time = {}
        self._cooldown_seconds = 60

    def should_alert(self, symbol: str) -> bool:
        """Check if we should send alert (cooldown check)."""
        now = time.time()
        last = self._last_alert_time.get(symbol, 0)
        if now - last < self._cooldown_seconds:
            return False
        self._last_alert_time[symbol] = now
        return True

    async def fire_crash_alert(self, symbol: str, drop_percent: float,
                               price_start: float, price_end: float,
                               time_window_min: int):
        """Fire all alert channels for a crash event."""
        if not self.should_alert(symbol):
            logger.debug(f"Alert cooldown active for {symbol}, skipping")
            return

        logger.warning(
            f"CRASH ALERT: {symbol} dropped {drop_percent:.1f}% "
            f"({price_start:.8g} -> {price_end:.8g}) in {time_window_min}min"
        )

        # Sound alert (runs in thread)
        self.sound.play_alert()

        # Telegram alert
        await self.telegram.send_crash_alert(
            symbol, drop_percent, price_start, price_end, time_window_min
        )

    async def fire_trade_update(self, symbol: str, pnl_percent: float,
                                pnl_eur: float, status: str):
        """Send trade update notification."""
        await self.telegram.send_trade_update(symbol, pnl_percent, pnl_eur, status)
