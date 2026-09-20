# scanner.py
# Live signal scanner — pulls fresh market data, evaluates strategies,
# and pushes PENDING signals to Supabase for dashboard review.
# NOTE: This is not a backtester. Historical validation lives in backtester.py.
import pandas as pd
import numpy as np
import talib
import config

from dotenv import load_dotenv
load_dotenv()

from database import DatabaseManager
import strategies
from data_provider import RobustDataProvider
from logger import get_logger

log = get_logger(__name__)

db = DatabaseManager()
provider = RobustDataProvider()


def is_duplicate_signal(ticker, timeframe, current_direction):
    tf = timeframe.upper()
    max_bars = config.DEDUP_LOOKBACK_BARS.get(timeframe, 5)
    bar_hours = 24 if timeframe == "1d" else 4
    cutoff = (pd.Timestamp.utcnow() - pd.Timedelta(hours=bar_hours * max_bars)).isoformat()

    try:
        response = db.client.table("signals") \
            .select("direction, created_at") \
            .eq("ticker", ticker) \
            .eq("timeframe", tf) \
            .eq("direction", current_direction) \
            .eq("status", "PENDING") \
            .gte("created_at", cutoff) \
            .limit(1) \
            .execute()
        return bool(response.data)
    except Exception as e:
        log.warning("Duplicate lookup failed for %s: %s", ticker, e)
        return False


def get_risk_bounds(ticker, signal, price, atr):
    if pd.isna(atr) or atr <= 0:
        log.debug("ATR invalid (%.4f) for %s — using 1.5%% of price",
                  atr if atr is not None else float("nan"), ticker)
        atr = price * 0.015

    profile = config.RISK_PROFILES.get(ticker, config.RISK_PROFILES["DEFAULT"])
    risk = atr * profile["sl"]
    reward = atr * profile["tp"]

    min_rr = getattr(config, "MIN_RR_RATIO", 1.5)
    if reward / risk < min_rr:
        original_reward = reward
        reward = risk * min_rr
        log.debug("R:R below minimum (%.2f) — TP expanded from %.2f to %.2f",
                  min_rr, original_reward, reward)

    if signal == "BUY":
        return price - risk, price + reward
    return price + risk, price - reward


def in_session(ticker):
    windows = config.SESSION_WINDOWS.get(ticker)
    if not windows:
        return True
    hour = pd.Timestamp.utcnow().hour
    return any(start <= hour < end for start, end in windows)


def build_weekly_context(df):
    try:
        weekly_df = df.resample('W-FRI').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
        }).dropna()

        min_bars = getattr(config, "MTF_MIN_WEEKLY_BARS", 30)
        if len(weekly_df) < min_bars:
            log.debug("Not enough weekly bars (%d < %d) — MTF gate disabled",
                      len(weekly_df), min_bars)
            return None, None

        w_close = weekly_df['close'].to_numpy().astype(float)
        period = getattr(config, "MTF_WEEKLY_SMA_PERIOD", 30)
        w_sma = talib.SMA(w_close, timeperiod=period)
        log.debug("Weekly context built: %d weeks, SMA period %d",
                  len(weekly_df), period)
        return w_close, w_sma
    except Exception as e:
        log.warning("Weekly resample failed: %s", e)
        return None, None


def scan_portfolio():
    log.info("Starting live S&P 500 signal scan")

    for timeframe, assets in config.WATCH_LIST.items():
        log.info("Timeframe %s — %d asset(s)", timeframe.upper(), len(assets))

        for asset in assets:
            try:
                if not in_session(asset):
                    log.info("Skipping %s: outside session window", asset)
                    continue

                lookback_days = 400
                df = provider.fetch_data(asset, timeframe, lookback_days)

                if df.empty or len(df) < 200:
                    log.warning("Skipping %s: insufficient data (%d bars)",
                                asset, len(df) if not df.empty else 0)
                    continue

                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df.columns = df.columns.str.lower()
                df = df.loc[~df.index.duplicated(keep="first")].sort_index().ffill().bfill()

                cl = df["close"].to_numpy().astype(float)
                hi = df["high"].to_numpy().astype(float)
                lw = df["low"].to_numpy().astype(float)

                atr = talib.ATR(hi, lw, cl, timeperiod=14)[-1]
                sma_200 = talib.SMA(cl, timeperiod=200)

                weekly_close = None
                weekly_sma = None
                if getattr(config, "MTF_ENABLED", False):
                    weekly_close, weekly_sma = build_weekly_context(df)

                vix_value = None
                try:
                    vix_df = provider.fetch_data("^VIX", "1d", 30)
                    if vix_df is not None and not vix_df.empty:
                        if isinstance(vix_df.columns, pd.MultiIndex):
                            vix_df.columns = vix_df.columns.get_level_values(0)
                        vix_df.columns = vix_df.columns.str.lower()
                        vix_value = vix_df["close"].to_numpy().astype(float)
                except Exception as e:
                    log.debug("VIX fetch skipped: %s", e)

                signal = strategies.evaluate_index(
                    cl, sma_200, vix_value, hi, lw,
                    weekly_close=weekly_close,
                    weekly_sma=weekly_sma,
                )

                if signal:
                    if is_duplicate_signal(asset, timeframe, signal):
                        log.info("Skipping %s: duplicate '%s' within window",
                                 asset, signal)
                        continue

                    cur_price = float(cl[-1])
                    sl, tp = get_risk_bounds(asset, signal, cur_price, atr)

                    db.insert_signal(
                        ticker=asset,
                        direction=signal,
                        price=cur_price,
                        sl=sl,
                        tp=tp,
                        timeframe=timeframe
                    )
                else:
                    log.info("No signal for %s on %s", asset, timeframe.upper())

            except Exception as e:
                log.exception("Error scanning %s on %s", asset, timeframe.upper())

    log.info("Scan complete")


if __name__ == "__main__":
    scan_portfolio()