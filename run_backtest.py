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
    if pd.isna(atr) or atr <= 0: atr = price * 0.015
    profile = config.RISK_PROFILES.get(ticker, config.RISK_PROFILES["DEFAULT"])
    
    risk = atr * profile["sl"]
    reward = atr * profile["tp"]
    
    if signal in ["BUY", "LONG_SPREAD"]:
        return price - risk, price + reward
    return price + risk, price - reward

def scan_portfolio():
    print(f"🏁 Starting Cloud Scanner across {len(config.WATCH_LIST)} instruments...")
    
    for asset in config.WATCH_LIST:
        try:
            df = yf.download(asset, period="1y", interval="1d")
            if df.empty or len(df) < 200: continue
            
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
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
                cur_price = float(cl[-1])
                sl, tp = get_risk_bounds(asset, signal, cur_price, atr)
                db.insert_signal(asset, signal, cur_price, sl, tp)
                
        except Exception as e:
            print(f"❌ Error scanning {asset}: {e}")

if __name__ == "__main__":
    scan_portfolio()
    print("🏆 Pipeline execution complete.")
