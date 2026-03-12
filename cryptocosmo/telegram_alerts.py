"""
Telegram alert integration for CryptoCosmo.

Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from environment variables.
If either is missing, all methods are silent no-ops — the bot runs fine without them.

Setup (one time):
  1. Message @BotFather on Telegram → /newbot → copy the token
  2. Message your bot, then visit:
     https://api.telegram.org/bot<TOKEN>/getUpdates
     and copy the chat_id from the response
  3. Add to your .env or shell:
     export TELEGRAM_BOT_TOKEN="123456:ABC..."
     export TELEGRAM_CHAT_ID="987654321"
"""

import logging
import os
from typing import Optional

import requests

_API_BASE = "https://api.telegram.org/bot{token}/sendMessage"
_TIMEOUT = 6


class TelegramAlerter:
    def __init__(self) -> None:
        self._token: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or None
        self._chat_id: Optional[str] = os.getenv("TELEGRAM_CHAT_ID", "").strip() or None
        if self._token and self._chat_id:
            logging.info(
                "TelegramAlerter: configured (chat_id=%s)", self._chat_id,
                extra={"action": "telegram_init"},
            )
        else:
            logging.info(
                "TelegramAlerter: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — alerts disabled",
                extra={"action": "telegram_init"},
            )

    @property
    def enabled(self) -> bool:
        return bool(self._token and self._chat_id)

    def send(self, message: str) -> None:
        """Fire and forget — logs warning on failure, never raises."""
        if not self.enabled:
            return
        url = _API_BASE.format(token=self._token)
        try:
            resp = requests.post(
                url,
                json={"chat_id": self._chat_id, "text": message, "parse_mode": "Markdown"},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logging.warning(
                "TelegramAlerter: failed to send message: %s",
                exc,
                extra={"action": "telegram_error"},
            )

    def alert_risk_paused(self, symbol: str, reason: Optional[str], equity: float, drawdown_pct: float) -> None:
        reason_text = reason or "threshold breached"
        msg = (
            f"⚠️ *CryptoCosmo — Risk Pause*\n"
            f"Symbol: `{symbol}`\n"
            f"Reason: {reason_text}\n"
            f"Equity: `{equity:.2f}`\n"
            f"Drawdown: `{drawdown_pct:.2f}%`"
        )
        self.send(msg)

    def alert_risk_resumed(self, symbol: str, equity: float) -> None:
        msg = (
            f"✅ *CryptoCosmo — Trading Resumed*\n"
            f"Symbol: `{symbol}`\n"
            f"Equity: `{equity:.2f}`"
        )
        self.send(msg)

    def alert_health_failure(self, symbol: str, error_streak: int) -> None:
        msg = (
            f"🔴 *CryptoCosmo — Health Failure*\n"
            f"Symbol: `{symbol}`\n"
            f"Error streak: `{error_streak}`\n"
            f"Bot loop is stopping."
        )
        self.send(msg)

    def alert_started(self, symbol: str, mode: str) -> None:
        msg = (
            f"🚀 *CryptoCosmo — Bot Started*\n"
            f"Symbol: `{symbol}`\n"
            f"Mode: `{mode}`"
        )
        self.send(msg)

    def alert_stopped(self, symbol: str) -> None:
        msg = f"⏹ *CryptoCosmo — Bot Stopped*\nSymbol: `{symbol}`"
        self.send(msg)
