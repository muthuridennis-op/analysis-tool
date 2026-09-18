import yfinance as yf
import pandas as pd
import numpy as np
import talib
import os
from supabase import create_client

def get_risk_params(ticker, signal_type, current_price):
    """
    Applies custom structural risk management limits based on asset volatility profiles
    """
    # 1. Equities Index Layout (S&P 500) -> Ultra tight control
    if ticker == "^GSPC":
        sl_pct = 0.01  # 1% Stop Loss
        tp_pct = 0.03  # 3% Take Profit
    # 2. Commodities Layers (WTI Crude Oil & Brent Crude) -> High Volatility buffer
    elif ticker in ["CL=F", "BZ=F"]:
        sl_pct = 0.04  # 4% Stop Loss
        tp_pct = 0.08  # 8% Take Profit
    # 3. Precious Metals Layer (Gold) -> Balanced Strategy
    elif ticker == "GC=F":
        sl_pct = 0.02  # 2% Stop Loss
        tp_pct = 0.05  # 5% Take Profit
    # 4. Standard Currencies Module (Forex) -> Default Strategy Rules
    else:
        sl_pct = 0.025 # 2.5% Stop Loss
        tp_pct = 0.06  # 6% Take Profit

    if signal_type == "BUY":
        sl_price = current_price * (1 - sl_pct)
        tp_price = current_price * (1 + tp_pct)
    else:
        sl_price = current_price * (1 + sl_pct)
        tp_price = current_price * (1 - tp_pct)
        
    return sl_price, tp_price

def process_asset(ticker, supabase_client):
    """Processes technical analysis logic for a single asset instrument"""
    print(f"📡 Downloading market data for {ticker}...")
    df = yf.download(ticker, period="1y", interval="1d")
    
    if df.empty or len(df) < 200:
        print(f"⚠️ Skipping {ticker}: Insufficient historical bar depth.")
        return

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = df.columns.str.lower()
    df = df.loc[~df.index.duplicated(keep="first")].sort_index().ffill().bfill()
    
    # --- INDICATOR CALCULATIONS ---
    close_prices = df["close"].to_numpy().astype(float)
    volume_data = df["volume"].to_numpy().astype(float)
    
    # 1. Moving Averages
    df["sma_50"] = talib.SMA(close_prices, timeperiod=50)
    df["sma_200"] = talib.SMA(close_prices, timeperiod=200)
    
    df["prev_sma_50"] = df["sma_50"].shift(1)
    df["prev_sma_200"] = df["sma_200"].shift(1)
    
    golden_cross = (df["sma_50"] > df["sma_200"]) & (df["prev_sma_50"] <= df["prev_sma_200"])
    death_cross = (df["sma_50"] < df["sma_200"]) & (df["prev_sma_50"] >= df["prev_sma_200"])
    
    # 2. Volume Filter
    df["volume_ma"] = talib.SMA(volume_data, timeperiod=20)
    high_volume = df["volume"] > df["volume_ma"]
    
    # --- EVALUATE RECENT BAR ---
    is_crossover = golden_cross.iloc[-1] or death_cross.iloc[-1]
    is_volume_valid = high_volume.iloc[-1]
    
    if is_crossover:
        if is_volume_valid:
            signal_type = "BUY" if golden_cross.iloc[-1] else "SELL"
            current_price = float(df["close"].iloc[-1])
            
            # Extract customized risk variables per asset class
            sl_price, tp_price = get_risk_params(ticker, signal_type, current_price)
                
            print(f"🚨 VALID SIGNAL: {ticker} {signal_type} verified at ${current_price:.4f}!")
            
            # Push Row to Supabase Data Layer
            supabase_client.table("signals").insert({
                "ticker": ticker,
                "direction": signal_type,
                "execution_price": current_price,
                "stop_loss": sl_price,
                "take_profit": tp_price,
                "status": "PENDING"
            }).execute()
        else:
            print(f"🔍 {ticker} crossover spotted, but rejected due to low market volume volume.")
    else:
        print(f"🔍 {ticker} scan clean. No structural trend breakouts.")

def run_pipeline():
    # Watchlist containing your exact required instruments
    watch_list = [
        "EURUSD=X", "GBPUSD=X", "AUDUSD=X", "USDJPY=X", "USDCAD=X", # Forex
        "^GSPC",                                                    # S&P 500 Index
        "GC=F",                                                     # Gold Futures
        "CL=F",                                                     # WTI Crude Oil Futures
        "BZ=F"                                                      # Brent Crude Oil Futures
    ]
    
    print(f"🏁 Starting portfolio scanner loop across {len(watch_list)} instruments...")
    
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    supabase = create_client(url, key)
    
    for asset in watch_list:
        try:
            process_asset(asset, supabase)
        except Exception as error:
            print(f"❌ Execution failure on instrument processing loop for {asset}: {error}")
            
    print("🏆 Cloud scanner cycle complete. All portfolio matrix evaluations updated.")

if __name__ == "__main__":
    run_pipeline()
