# data_provider.py
import os
import yfinance as yf
import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame as AlpacaTimeFrame

from logger import get_logger

log = get_logger(__name__)


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
        tf_lower = timeframe.lower()
        end_dt = pd.Timestamp.now(tz='UTC')
        start_dt = end_dt - pd.Timedelta(days=lookback_days)

        # ROUTE 1: ALPACA
        if self.alpaca_client and not ticker.endswith("=F") and not ticker.endswith("=X"):
            try:
                alpaca_tf = AlpacaTimeFrame.Day if tf_lower == "1d" else AlpacaTimeFrame.Hour
                symbol = "SPY" if ticker == "^GSPC" else ticker

                request_params = StockBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=alpaca_tf,
                    start=start_dt,
                    end=end_dt
                )
                bars = self.alpaca_client.get_stock_bars(request_params)

                if bars and not bars.df.empty:
                    df = bars.df.reset_index()
                    df = df.set_index('timestamp')
                    df = df[['open', 'high', 'low', 'close', 'volume']]
                    log.info("Data fetched via Alpaca for %s (%d bars)", ticker, len(df))
                    return df
            except Exception as e:
                log.warning("Alpaca fetch failed for %s: %s — falling back to yfinance",
                            ticker, e)

        # ROUTE 2: YAHOO FINANCE
        try:
            df = yf.download(
                ticker,
                start=start_dt.strftime('%Y-%m-%d'),
                end=end_dt.strftime('%Y-%m-%d'),
                interval=timeframe,
                progress=False
            )

            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df.columns = df.columns.str.lower()
                log.info("Data fetched via yfinance for %s (%d bars)", ticker, len(df))
                return df

            log.warning("yfinance returned empty frame for %s", ticker)
        except Exception as e:
            log.error("All data sources failed for %s: %s", ticker, e)

        return pd.DataFrame()