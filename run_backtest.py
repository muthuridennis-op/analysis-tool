import yfinance as yf
import pandas as pd
import numpy as np
import talib
import os
from supabase import create_client

def run_pipeline():
    print("📥 Fetching real-time market data in the cloud...")
    # Change "EURUSD=X" to "AAPL" or any asset ticker you want to scan!
    ticker = "EURUSD=X" 
    df = yf.download(ticker, period="1y", interval="1d")
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = df.columns.str.lower()
    df = df.loc[~df.index.duplicated(keep="first")].sort_index().ffill().bfill()
    
    # --- INDICATOR CALCULATIONS ---
    close_prices = df["close"].to_numpy().astype(float)
    volume_data = df["volume"].to_numpy().astype(float)
    
    # 1. Trend Indicators (Moving Averages)
    df["sma_50"] = talib.SMA(close_prices, timeperiod=50)
    df["sma_200"] = talib.SMA(close_prices, timeperiod=200)
    
    df["prev_sma_50"] = df["sma_50"].shift(1)
    df["prev_sma_200"] = df["sma_200"].shift(1)
    
    golden_cross = (df["sma_50"] > df["sma_200"]) & (df["prev_sma_50"] <= df["prev_sma_200"])
    death_cross = (df["sma_50"] < df["sma_200"]) & (df["prev_sma_50"] >= df["prev_sma_200"])
    
    # 2. Advanced Volume Filter (Calculates 20-day Average Volume)
    df["volume_ma"] = talib.SMA(volume_data, timeperiod=20)
    high_volume = df["volume"] > df["volume_ma"]
    
    # --- SIGNAL VERIFICATION ENGINE ---
    is_crossover = golden_cross.iloc[-1] or death_cross.iloc[-1]
    is_volume_valid = high_volume.iloc[-1]
    
    if is_crossover:
        if is_volume_valid:
            signal_type = "BUY" if golden_cross.iloc[-1] else "SELL"
            current_price = float(df["close"].iloc[-1])
            
            # --- CALCULATE RISK MANAGEMENT THRESHOLDS ---
            if signal_type == "BUY":
                sl_price = current_price * 0.97  # 3% stop loss below
                tp_price = current_price * 1.06  # 6% take profit above
            else:
                sl_price = current_price * 1.03  # 3% stop loss above
                tp_price = current_price * 0.94  # 6% take profit below
                
            print(f"🚨 VALID SIGNAL: {signal_type} crossover verified. Updating database...")
            
            # Connect to Supabase Cloud Database Layer
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_KEY")
            supabase = create_client(url, key)
            
            supabase.table("signals").insert({
                "ticker": ticker,
                "direction": signal_type,
                "execution_price": current_price,
                "stop_loss": sl_price,
                "take_profit": tp_price,
                "status": "PENDING"
            }).execute()
            print("🚀 Signal pushed successfully to database layer.")
        else:
            print("🔍 Crossover spotted, but REJECTED due to low institutional volume (Sideways Market).")
    else:
        print("🔍 Scanning Complete: No structural technical patterns registered on this bar.")

if __name__ == "__main__":
    run_pipeline()
