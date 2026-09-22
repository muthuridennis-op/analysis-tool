# outcome_tracker.py
"""
Polls market prices for PENDING/MANUALLY_TRADED signals and auto-closes
them when SL or TP is hit. Signals exceeding MAX_AGE_DAYS become CLOSED_TIME.

Run this on a schedule (e.g. hourly) alongside the scanner.
"""
import pandas as pd
import yfinance as yf

from dotenv import load_dotenv
load_dotenv()

from database import DatabaseManager
from logger import get_logger
from timeutils import utcnow, to_utc, daily_index_to_utc
import config

log = get_logger(__name__)
db = DatabaseManager()


def _fetch_recent_prices(ticker: str, since: pd.Timestamp) -> pd.DataFrame:
    df = yf.download(
        ticker,
        start=since.strftime("%Y-%m-%d"),
        interval="1d",
        progress=False,
    )
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = df.columns.str.lower()

    if isinstance(df.index, pd.DatetimeIndex):
        if df.index.tz is None:
            df.index = daily_index_to_utc(df.index)
        else:
            df.index = df.index.tz_convert("UTC")
    return df


def _evaluate_signal(sig: dict, prices: pd.DataFrame):
    created_at = to_utc(sig["created_at"])
    direction = sig["direction"]
    sl = float(sig["stop_loss"]) if sig.get("stop_loss") else None
    tp = float(sig["take_profit"]) if sig.get("take_profit") else None

    if sl is None or tp is None:
        return None, None, None

    eligible = prices[prices.index > created_at]
    if eligible.empty:
        return None, None, None

    for ts, row in eligible.iterrows():
        op = float(row["open"])
        hi = float(row["high"])
        lo = float(row["low"])

        if direction == "BUY":
            if op <= sl:
                return "CLOSED_SL", op, ts
            if op >= tp:
                return "CLOSED_TP", op, ts
            if lo <= sl:
                return "CLOSED_SL", sl, ts
            if hi >= tp:
                return "CLOSED_TP", tp, ts
        else:
            if op >= sl:
                return "CLOSED_SL", op, ts
            if op <= tp:
                return "CLOSED_TP", op, ts
            if hi >= sl:
                return "CLOSED_SL", sl, ts
            if lo <= tp:
                return "CLOSED_TP", tp, ts

    max_age = getattr(config, "OUTCOME_MAX_AGE_DAYS", 45)
    age_days = (utcnow() - created_at).days
    if age_days >= max_age:
        last_close = float(eligible["close"].iloc[-1])
        return "CLOSED_TIME", last_close, eligible.index[-1]

    return None, None, None


def process_outcomes():
    log.info("Running outcome tracker sweep...")

    try:
        resp = db.client.table("signals") \
            .select("*") \
            .in_("status", ["PENDING", "MANUALLY_TRADED"]) \
            .execute()
        signals = resp.data
    except Exception as e:
        log.error("Failed to load signals: %s", e)
        return

    if not signals:
        log.info("No open signals to process.")
        return

    log.info("Processing %d open signal(s)", len(signals))

    by_ticker = {}
    for s in signals:
        by_ticker.setdefault(s["ticker"], []).append(s)

    closed = 0
    for ticker, sigs in by_ticker.items():
        earliest = min(to_utc(s["created_at"]) for s in sigs)
        try:
            prices = _fetch_recent_prices(ticker, earliest - pd.Timedelta(days=2))
        except Exception as e:
            log.warning("Price fetch failed for %s: %s", ticker, e)
            continue

        if prices.empty:
            log.warning("Empty price history for %s", ticker)
            continue

        for sig in sigs:
            try:
                status, exit_price, exit_ts = _evaluate_signal(sig, prices)
                if status is None:
                    continue

                db.client.table("signals").update({
                    "status": status,
                    "exit_price": float(exit_price),
                    "exit_at": exit_ts.isoformat(),
                }).eq("id", sig["id"]).execute()

                log.info(
                    "Signal %s (%s %s) → %s @ %.2f",
                    sig["id"], ticker, sig["direction"], status, exit_price
                )
                closed += 1
            except Exception as e:
                log.exception("Error evaluating signal %s: %s", sig.get("id"), e)

    log.info("Outcome sweep complete — %d signal(s) closed.", closed)


if __name__ == "__main__":
    process_outcomes()