# data_provider.py
import os
import yfinance as yf
import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame as AlpacaTimeFrame
from ib_insync import IB, Future, Index, util

class RobustDataProvider:
    def __init__(self):
        # 🔑 Initialize Alpaca Historical Data Client Layer
        self.alpaca_key = os.environ.get("ALPACA_API_KEY")
        self.alpaca_secret = os.environ.get("ALPACA_SECRET_KEY")
        
        if self.alpaca_key and self.alpaca_secret:
            try:
                self.alpaca_client = StockHistoricalDataClient(self.alpaca_key, self.alpaca_secret)
                print("🔌 Alpaca API client initialized successfully.")
            except Exception as e:
                print(f"⚠️ Error initializing Alpaca Client: {e}")
                self.alpaca_client = None
        else:
            self.alpaca_client = None
            print("⚠️ Alpaca API credentials missing from environment. Alpaca source bypassed.")

    def fetch_data(self, ticker: str, timeframe: str, lookback_days: int) -> pd.DataFrame:
        """
        Attempts execution across live institutional API architectures, 
        standardizing columns to lowercase ['open', 'high', 'low', 'close', 'volume'].
        """
        tf_lower = timeframe.lower()
        end_dt = pd.Timestamp.now(tz='UTC')
        start_dt = end_dt - pd.Timedelta(days=lookback_days)

        # ==========================================
        # ROUTE 1: ALPACA API (Indices & US Equities)
        # ==========================================
        # Skips Futures (=F) and Forex (=X) which require separate Alpaca agreements
        if self.alpaca_client and not ticker.endswith("=F") and not ticker.endswith("=X"):
            try:
                # Map system strings to Alpaca enum timeframes
                alpaca_tf = AlpacaTimeFrame.Day if tf_lower == "1d" else AlpacaTimeFrame.Hour
                
                # Transform ticker syntax to match standard asset tracking formats
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
                    print(f"✅ Data fetched via [Alpaca] for {ticker}")
                    return df
            except Exception as e:
                print(f"⚠️ Alpaca data fetch failed for {ticker}: {e}. Retrying via alternatives...")

        # ==========================================
        # ROUTE 2: INTERACTIVE BROKERS (IBKR Futures/Forex)
        # ==========================================
        # Requires local/containerized TWS or IB Gateway running on designated network port
        if os.environ.get("IBKR_ENABLED") == "TRUE":
            try:
                ib = IB()
                # Default ports: 7497 (TWS paper), 4002 (Gateway paper)
                ib_port = int(os.environ.get("IBKR_PORT", 7497))
                ib.connect(os.environ.get("IBKR_HOST", "127.0.0.1"), ib_port, clientId=99)
                
                contract = None
                
                # Structural parsing for specific asset rules
                if ticker == "^GSPC":
                    contract = Index('SPX', 'CBOE')
                elif ticker == "GC=F":
                    contract = Future('GC', '202612', 'COMEX')  # Standardize to valid current expiration
                elif ticker == "CL=F":
                    contract = Future('CL', '202612', 'NYMEX')
                elif ticker == "BZ=F":
                    contract = Future('BZ', '202612', 'NYMEX')
                elif ticker.endswith("=X"):
                    # Forex parsing (e.g., EURUSD=X to EUR base, USD cash pair)
                    base_currency = ticker[0:3]
                    quote_currency = ticker[3:6]
                    from ib_insync import Forex
                    contract = Forex(f"{base_currency}{quote_currency}")

                if contract:
                    ib.qualifyContracts(contract)
                    duration = f"{lookback_days} D"
                    bar_size = "1 day" if tf_lower == "1d" else "4 hours"
                    
                    bars = ib.reqHistoricalData(
                        contract, 
                        endDateTime='', 
                        durationStr=duration,
                        barSizeSetting=bar_size, 
                        whatToShow='MIDPOINT' if ticker.endswith("=X") else 'TRADES', 
                        useRTH=True
                    )
                    ib.disconnect()
                    
                    if bars:
                        df = util.df(bars)
                        df = df.set_index('date')
                        df = df[['open', 'high', 'low', 'close', 'volume']]
                        print(f"✅ Data fetched via [IBKR] for {ticker}")
                        return df
            except Exception as e:
                print(f"⚠️ Interactive Brokers fetch failed for {ticker}: {e}. Retrying via fallback...")

        # ==========================================
        # ROUTE 3: YAHOO FINANCE (Global Resilience Fallback)
        # ==========================================
        try:
            lookback_str = f"{lookback_days}d"
            df = yf.download(ticker, start=start_dt.strftime('%Y-%m-%d'), end=end_dt.strftime('%Y-%m-%d'), interval=timeframe, progress=False)
            if not df.empty:
                print(f"ℹ️ Data fetched via [yfinance Fallback] for {ticker}")
                return df
        except Exception as e:
            print(f"❌ Critical failure: All data sources failed for {ticker}. Error: {e}")
            
        return pd.DataFrame()  # Return safe empty frame structural type on complete failure
