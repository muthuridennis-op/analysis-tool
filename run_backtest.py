# run_backtest.py
import yfinance as yf
import pandas as pd
import numpy as np
import talib
import config
from database import DatabaseManager
import strategies

db = DatabaseManager()

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
    
    # Outer Loop: Scans keys inside WATCH_LIST ("1d", "4h")
    for timeframe, assets in config.WATCH_LIST.items():
        print(f"\n⏳ Processing Timeframe Horizon: {timeframe.upper()} ({len(assets)} assets)")
        
        for asset in assets:
            try:
                # Dynamic lookback window mapping: 1 year for daily, 60 days for 4-hour
                lookback = "1y" if timeframe == "1d" else "60d"
                
                df = yf.download(asset, period=lookback, interval=timeframe)
                if df.empty or len(df) < 50: 
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
                # --- STRATEGY ROUTER MATRIX ---
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
                    cur_price = float(cl[-1])
                    sl, tp = get_risk_bounds(asset, signal, cur_price, atr)
                    
                    # Formats title string layout dynamically (e.g. "EURUSD=X (4H)")
                    labeled_ticker = f"{asset} ({timeframe.upper()})"
                    db.insert_signal(labeled_ticker, signal, cur_price, sl, tp)
                    
            except Exception as e:
                print(f"❌ Error scanning {asset} on {timeframe.upper()}: {e}")

if __name__ == "__main__":
    scan_portfolio()
    print("\n🏆 Multi-timeframe processing cycle complete.")
