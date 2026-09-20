# database.py
import os
import sys
from supabase import create_client

from logger import get_logger

log = get_logger(__name__)


class DatabaseManager:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")

        if not url or not key:
            log.critical("Database credentials missing from environment.")
            sys.exit(1)

        try:
            self.client = create_client(url, key)
            log.info("Database client initialized.")
        except Exception as e:
            log.critical("Database connection initialization failed: %s", e)
            sys.exit(1)

    def insert_signal(self, ticker, direction, price, sl, tp, timeframe):
        try:
            payload = {
                "ticker": ticker,
                "direction": direction,
                "execution_price": float(price),
                "stop_loss": float(sl),
                "take_profit": float(tp),
                "status": "PENDING",
                "timeframe": timeframe.upper()
            }
            self.client.table("signals").insert(payload).execute()
            log.info("Signal uploaded: %s %s @ %.2f (SL=%.2f TP=%.2f TF=%s)",
                     ticker, direction, price, sl, tp, timeframe.upper())
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