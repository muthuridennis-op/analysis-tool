# database.py
import os
import sys
import httpx
from supabase import create_client

from logger import get_logger

log = get_logger(__name__)


def _send_telegram(ticker, direction, price, sl, tp, timeframe, size_info=None):
    """Fire-and-forget Telegram notification. Never raises."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        return

    try:
        emoji = "🟢" if direction == "BUY" else "🔴"
        lines = [
            f"{emoji} *{direction} {ticker}*",
            f"Entry: `{price:.2f}`",
            f"SL: `{sl:.2f}`",
            f"TP: `{tp:.2f}`",
            f"TF: {timeframe.upper()}",
        ]
        if size_info:
            lines.append(
                f"Size: `{size_info['units']:g} {size_info['instrument']}` "
                f"(risk ≈ ${size_info['risk_cash']:.2f})"
            )

        httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": "\n".join(lines),
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
        log.info("Telegram notification sent for %s %s", direction, ticker)
    except Exception as e:
        log.warning("Telegram notify failed: %s", e)


class DatabaseManager:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        # Backend uses SERVICE key (bypasses RLS). Fall back to anon key.
        key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")

        if not url or not key:
            log.critical("Database credentials missing from environment.")
            sys.exit(1)

        try:
            self.client = create_client(url, key)
            log.info("Database client initialized.")
        except Exception as e:
            log.critical("Database connection initialization failed: %s", e)
            sys.exit(1)

    def insert_signal(self, ticker, direction, price, sl, tp, timeframe, size_info=None):
        try:
            payload = {
                "ticker": ticker,
                "direction": direction,
                "execution_price": float(price),
                "stop_loss": float(sl),
                "take_profit": float(tp),
                "status": "PENDING",
                "timeframe": timeframe.upper(),
            }
            if size_info:
                payload.update({
                    "size_units": float(size_info["units"]),
                    "size_instrument": size_info["instrument"],
                    "risk_cash": float(size_info["risk_cash"]),
                })
            self.client.table("signals").insert(payload).execute()
            log.info(
                "Signal uploaded: %s %s @ %.2f (SL=%.2f TP=%.2f TF=%s%s)",
                ticker, direction, price, sl, tp, timeframe.upper(),
                f" size={size_info['units']:g} {size_info['instrument']}"
                if size_info else "",
            )
            # Notify via Telegram (no-op if creds missing)
            _send_telegram(ticker, direction, price, sl, tp, timeframe, size_info)
        except Exception as error:
            log.error("Failed to commit signal for %s: %s", ticker, error)

    def update_signal_status(self, signal_id, new_status):
        try:
            self.client.table("signals").update(
                {"status": new_status}
            ).eq("id", signal_id).execute()
            log.info("Signal %s updated to %s", signal_id, new_status)
        except Exception as error:
            log.error("Failed to update signal %s: %s", signal_id, error)