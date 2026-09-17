import yfinance as yf
import pandas as pd
import numpy as np
import talib
import os
from supabase import create_client

def run_pipeline():
    print("📥 Fetching real-time market data in the cloud...")
    # Download historical data dynamically into cloud environment memory
    df = yf.download("AAPL", period="1y", interval="1d")
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = df.columns.str.lower()
    df = df.loc[~df.index.duplicated(keep="first")].sort_index().ffill().bfill()
    
    print("📊 Calculating indicators (SMA 50 and SMA 200)...")
    # Extract technical parameters matching your notebook algorithm logic
    close_prices = df["close"].to_numpy().astype(float)
    df["sma_50"] = talib.SMA(close_prices, timeperiod=50)
    df["sma_200"] = talib.SMA(close_prices, timeperiod=200)
    
    df["prev_sma_50"] = df["sma_50"].shift(1)
    df["prev_sma_200"] = df["sma_200"].shift(1)
    
    golden_cross = (df["sma_50"] > df["sma_200"]) & (df["prev_sma_50"] <= df["prev_sma_200"])
    death_cross = (df["sma_50"] < df["sma_200"]) & (df["prev_sma_50"] >= df["prev_sma_200"])
    
    # Check the immediate final row representing today's active status
    if golden_cross.iloc[-1] or death_cross.iloc[-1]:
        signal_type = "BUY" if golden_cross.iloc[-1] else "SELL"
        current_price = float(df["close"].iloc[-1])
        
        print(f"🚨 ALERT: {signal_type} crossover detected! Pushing to database...")
        
        # Connect to Supabase to update your phone dashboard
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        
        if not url or not key:
            print("⚠️ Error: Supabase credentials are missing from environment variables.")
            return
            
        supabase = create_client(url, key)
        
        supabase.table("signals").insert({
            "ticker": "AAPL",
            "direction": signal_type,
            "execution_price": current_price,
            "status": "PENDING"
        }).execute()
        print(f"🚀 Signal {signal_type} pushed successfully to database layer.")
    else:
        print("🔍 Scanning Complete: No crossover patterns registered on the current bar.")

if __name__ == "__main__":
    run_pipeline()
