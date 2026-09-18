# run_backtest.py
import yfinance as yf
import pandas as pd
import numpy as np
import talib
import config

from dotenv import load_file, load_dotenv
load_dotenv() #This scsns your project root for .env and loads the variables
from database import DatabaseManager
import strategies
from data_provider import RobustDataProvider  # New multi-source data integration

# Initialize managers and robust multi-source data provider
db = DatabaseManager()
provider = RobustDataProvider()

def is_duplicate_signal(ticker, timeframe, current_direction):
    """
    Queries Supabase for the most recent entry matching the asset and timeframe.
    Returns True if the latest signal shares the same direction, preventing spams.
    """
    try:
        # Fetch only the single most recent record for this asset + timeframe configuration
        response = db.client.table("signals") \
            .select("direction, status") \
            .eq("ticker", ticker) \
            .eq("timeframe", timeframe.upper()) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
            
        if response.data:
            latest_record = response.data[0]
            # Match condition: If the trend direction is identical, flag it as a duplicate
            if latest_record["direction"] == current_direction:
                return True
    except Exception as e:
        # Fallback safety: If database lookup fails, log error and allow execution
        print(f"⚠️ Warning during duplicate safety lookup: {e}")
        
    return False

def get_risk_bounds(ticker, signal, price, atr):
    if pd.isna(atr) or atr <= 0: 
        atr = price * 0.015
    profile = config.RISK_PROFILES.get(ticker, config.RISK_PROFILES["DEFAULT"])
    
    risk = atr * profile["sl"]
    reward = atr * profile["tp"]
    
    if signal in ["BUY", "LONG_SPREAD"]:
        return price - risk, price + reward
    return price + risk, price - reward

def scan_portfolio():
    print("🏁 Starting Multi-Timeframe Cloud Scanner Engine...")
    
    for timeframe, assets in config.WATCH_LIST.items():
        print(f"\n⏳ Processing Timeframe Horizon: {timeframe.upper()} ({len(assets)} assets)")
        
        for asset in assets:
            try:
                # Dynamically set lookback context constraints
                lookback_days = 365 if timeframe == "1d" else 60
                
                # Fetching via robust fallback array (Alpaca -> IBKR -> yfinance)
                df = provider.fetch_data(asset, timeframe, lookback_days)
                
                if df.empty or len(df) < 50: 
                    print(f"⏭️ Skipping {asset} ({timeframe.upper()}): Insufficient data or empty frame.")
                    continue
                
                if isinstance(df.columns, pd.MultiIndex): 
                    df.columns = df.columns.get_level_values(0)
                df.columns = df.columns.str.lower()
                df = df.loc[~df.index.duplicated(keep="first")].sort_index().ffill().bfill()
                
                cl = df["close"].to_numpy().astype(float)
                hi = df["high"].to_numpy().astype(float)
                lw = df["low"].to_numpy().astype(float)
                vol = df["volume"].to_numpy().astype(float)
                
                atr = talib.ATR(hi, lw, cl, timeperiod=14)[-1]
                vol_ma = talib.SMA(vol, timeperiod=20)
                
                signal = None
                
                if asset in ["EURUSD=X", "GBPUSD=X", "AUDUSD=X", "USDJPY=X", "USDCAD=X"]:
                    signal = strategies.evaluate_forex(cl)
                elif asset == "^GSPC":
                    sma_200 = talib.SMA(cl, timeperiod=200)
                    signal = strategies.evaluate_index(cl, sma_200)
                elif asset == "GC=F":
                    up, mid, low = talib.BBANDS(cl, timeperiod=20, nbdevup=2, nbdevdn=2)
                    signal = strategies.evaluate_gold(cl, up, low, vol, vol_ma)
                elif asset in ["CL=F", "BZ=F"]:
                    macd, sig, hist = talib.MACD(cl, fastperiod=12, slowperiod=26, signalperiod=9)
                    signal = strategies.evaluate_oil(macd, sig, vol, vol_ma)
                    
                if signal:
                    # DEDUPLICATION CONSTRAINT STEP: 
                    # If this asset printed the exact same signal during the last loop, skip it.
                    if is_duplicate_signal(asset, timeframe, signal):
                        print(f"⏭️  Skipping {asset} ({timeframe.upper()}): Consecutive duplicate '{signal}' alert detected.")
                        continue
                        
                    cur_price = float(cl[-1])
                    sl, tp = get_risk_bounds(asset, signal, cur_price, atr)
                    
                    payload = {
                        "ticker": asset,
                        "direction": signal,
                        "execution_price": cur_price,
                        "stop_loss": sl,
                        "take_profit": tp,
                        "status": "PENDING",
                        "timeframe": timeframe.upper()
                    }
                    
                    # Commit distinct unique row data to Supabase Database table
                    db.client.table("signals").insert(payload).execute()
                    print(f"🚀 Signal uploaded successfully for {asset} ({timeframe.upper()}).")
                    
            except Exception as e:
                print(f"❌ Error scanning {asset} on {timeframe.upper()}: {e}")

if __name__ == "__main__":
    scan_portfolio()
    print("\n🏆 Multi-timeframe processing cycle complete.")
