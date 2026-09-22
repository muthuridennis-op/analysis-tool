# data_provider.py
import os
import time
import pandas as pd
import yfinance as yf
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame as AlpacaTimeFrame

from logger import get_logger
from timeutils import daily_index_to_utc

log = get_logger(__name__)

# Alpaca doesn't natively serve these symbols.
# None = skip Alpaca entirely and go straight to yfinance.
SYMBOL_MAP = {
    "^GSPC": "SPY",
    "^VIX":  None,
}


def _retry(fn, attempts=3, base_delay=1.0):
    """Simple exponential backoff. Raises the last error on exhaustion."""
    last_err = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last_err = e
            time.sleep(base_delay * (2 ** i))
    raise last_err


def _validate_freshness(df: pd.DataFrame, max_stale_days: int = 5) -> bool:
    """Returns True if the last bar is recent enough."""
    if df.empty:
        return False
    last = df.index[-1]
    if not isinstance(last, pd.Timestamp):
        last = pd.Timestamp(last)
    if last.tzinfo is None:
        last = last.tz_localize("UTC")
    age_days = (pd.Timestamp.now(tz="UTC") - last).days
    if age_days > max_stale_days:
        log.warning("Stale data: last bar %s (%d days old)", last, age_days)
        return False
    return True


class RobustDataProvider:
    def __init__(self):
        self.alpaca_key = os.environ.get("ALPACA_API_KEY")
        self.alpaca_secret = os.environ.get("ALPACA_SECRET_KEY")

        if self.alpaca_key and self.alpaca_secret:
            try:
                self.alpaca_client = StockHistoricalDataClient(
                    self.alpaca_key, self.alpaca_secret
                )
                log.info("Alpaca API client initialized.")
            except Exception as e:
                log.warning("Alpaca init failed: %s", e)
                self.alpaca_client = None
        else:
            self.alpaca_client = None
            log.warning("Alpaca credentials missing — Alpaca route bypassed.")

    def fetch_data(self, ticker: str, timeframe: str, lookback_days: int) -> pd.DataFrame:
        """
        Returns an OHLCV DataFrame with attrs['source'] in {"alpaca","yfinance","none"}.
        Index is UTC-aware for daily bars.
        """
        tf_lower = timeframe.lower()
        end_dt = pd.Timestamp.now(tz="UTC")
        start_dt = end_dt - pd.Timedelta(days=lookback_days)

        # Resolve Alpaca symbol mapping. None = explicitly skip Alpaca.
        mapped = SYMBOL_MAP.get(ticker, ticker)

        # ROUTE 1: ALPACA
        if (self.alpaca_client and mapped is not None
                and not ticker.endswith("=F") and not ticker.endswith("=X")):
            try:
                alpaca_tf = AlpacaTimeFrame.Day if tf_lower == "1d" else AlpacaTimeFrame.Hour
                symbol = mapped

                def _fetch_alpaca():
                    req = StockBarsRequest(
                        symbol_or_symbols=symbol,
                        timeframe=alpaca_tf,
                        start=start_dt,
                        end=end_dt,
                    )
                    return self.alpaca_client.get_stock_bars(req)

                bars = _retry(_fetch_alpaca, attempts=3, base_delay=1.0)

                if bars and not bars.df.empty:
                    df = bars.df.reset_index().set_index("timestamp")
                    df = df[["open", "high", "low", "close", "volume"]]
                    df.index = pd.DatetimeIndex(df.index)
                    if df.index.tz is None:
                        df.index = df.index.tz_localize("UTC")
                    else:
                        df.index = df.index.tz_convert("UTC")
                    if _validate_freshness(df):
                        df.attrs["source"] = "alpaca"
                        log.info("Data fetched via Alpaca for %s (%d bars)", ticker, len(df))
                        return df
                    log.warning("Alpaca data stale for %s — falling back", ticker)
            except Exception as e:
                log.warning("Alpaca fetch failed for %s: %s — falling back to yfinance",
                            ticker, e)

        # ROUTE 2: YAHOO FINANCE
        try:
            def _fetch_yf():
                return yf.download(
                    ticker,
                    start=start_dt.strftime("%Y-%m-%d"),
                    end=end_dt.strftime("%Y-%m-%d"),
                    interval=timeframe,
                    progress=False,
                )

            df = _retry(_fetch_yf, attempts=3, base_delay=1.0)

            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df.columns = df.columns.str.lower()
                # Normalize daily-bar index to UTC-aware
                if isinstance(df.index, pd.DatetimeIndex):
                    if df.index.tz is None:
                        df.index = daily_index_to_utc(df.index)
                    else:
                        df.index = df.index.tz_convert("UTC")

                if _validate_freshness(df):
                    df.attrs["source"] = "yfinance"
                    log.info("Data fetched via yfinance for %s (%d bars)", ticker, len(df))
                    return df
                log.warning("yfinance data stale for %s", ticker)
            else:
                log.warning("yfinance returned empty frame for %s", ticker)
        except Exception as e:
            log.error("All data sources failed for %s: %s", ticker, e)

        empty = pd.DataFrame()
        empty.attrs["source"] = "none"
        return empty