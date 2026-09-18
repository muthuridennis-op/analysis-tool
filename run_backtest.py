import yfinance as yf
import pandas as pd
import numpy as np
import talib
import os
import sys
from supabase import create_client

# ==============================================================================
# 🛡️ SYSTEM RISK PROFILER
# ==============================================================================
def get_risk_params(ticker, signal_type, current_price):
    if ticker == "^GSPC":
        sl_pct = 0.01  # 1% Stop Loss
        tp_pct = 0.03  # 3% Take Profit
    elif ticker in ["CL=F", "BZ=F", "OIL_ARB_SPREAD"]:
        sl_pct = 0.04  # 4% Stop Loss
        tp_pct = 0.08  # 8% Take Profit
    elif ticker == "GC=F":
        sl_pct = 0.02  # 2% Stop Loss
        tp_pct = 0.05  # 5% Take Profit
    else:
        sl_pct = 0.025 # 2.5% Stop Loss
        tp_pct = 0.06  # 6% Take Profit

    if signal_type == "BUY" or signal_type == "LONG_SPREAD":
        sl_price = current_price * (1 - sl_pct)
        tp_price = current_price * (1 + tp_pct)
    else:
        sl_price = current_price * (1 + sl_pct)
        tp_price = current_price * (1 - tp_pct)
        
    return sl_price, tp_price

# ==============================================================================
# 📊 TECHNICAL STRATEGY ENGINES
# ==============================================================================
def execute_asset_strategy(ticker, df):
    close_prices = df["close"].to_numpy().astype(float)
    volume_data = df["volume"].to_numpy().astype(float)
    current_price = float(df["close"].iloc[-1])
    
    if ticker in ["EURUSD=X", "GBPUSD=X", "AUDUSD=X", "USDJPY=X", "USDCAD=X"]:
        df["ema_20"] = talib.EMA(close_prices, timeperiod=20)
        df["ema_50"] = talib.EMA(close_prices, timeperiod=50)
        df["rsi"] = talib.RSI(close_prices, timeperiod=14)
        
        ema_cross_up = (df["ema_20"] > df["ema_50"]) & (df["ema_20"].shift(1) <= df["ema_50"].shift(1))
        ema_cross_down = (df["ema_20"] < df["ema_50"]) & (df["ema_20"].shift(1) >= df["ema_50"].shift(1))
        
        if ema_cross_up.iloc[-1] and (50 < df["rsi"].iloc[-1] < 65):
            return "BUY", current_price
        elif ema_cross_down.iloc[-1] and (35 < df["rsi"].iloc[-1] < 50):
            return "SELL", current_price

    elif ticker == "^GSPC":
        df["sma_200"] = talib.SMA(close_prices, timeperiod=200)
        df["rsi_2"] = talib.RSI(close_prices, timeperiod=2)
        
        if (df["close"].iloc[-1] > df["sma_200"].iloc[-1]) and (df["rsi_2"].iloc[-1] < 10):
            return "BUY", current_price
        elif (df["close"].iloc[-1] < df["sma_200"].iloc[-1]) and (df["rsi_2"].iloc[-1] > 90):
            return "SELL", current_price

    elif ticker == "GC=F":
        df["volume_ma"] = talib.SMA(volume_data, timeperiod=20)
        upper, middle, lower = talib.BBANDS(close_prices, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
        
        breakout_up = (df["close"] > upper) & (df["close"].shift(1) <= upper.shift(1))
        breakout_down = (df["close"] < lower) & (df["close"].shift(1) >= lower.shift(1))
        volume_confirmed = df["volume"] > df["volume_ma"]
        
        if breakout_up.iloc[-1] and volume_confirmed.iloc[-1]:
            return "BUY", current_price
        elif breakout_down.iloc[-1] and volume_confirmed.iloc[-1]:
            return "SELL", current_price

    elif ticker in ["CL=F", "BZ=F"]:
        df["volume_ma"] = talib.SMA(volume_data, timeperiod=20)
        macd, signal, hist = talib.MACD(close_prices, fastperiod=12, slowperiod=26, signalperiod=9)
        
        macd_cross_up = (macd > signal) & (macd.shift(1) <= signal.shift(1))
        macd_cross_down = (macd < signal) & (macd.shift(1) >= signal.shift(1))
        volume_confirmed = df["volume"] > df["volume_ma"]
        
        if macd_cross_up.iloc[-1] and volume_confirmed.iloc[-1]:
            return "BUY", current_price
        elif macd_cross_down.iloc[-1] and volume_confirmed.iloc[-1]:
            return "SELL", current_price

    return None, None

# ==============================================================================
# ⛓️ STATISTICAL ARBITRAGE ENGINE (PAIRS SPREAD REVERSION)
# ==============================================================================
def execute_statistical_arbitrage(supabase_client):
    print("⛓️ Running Statistical Arbitrage Engine (Brent vs WTI Oil)...")
    try:
        brent = yf.download("BZ=F", period="1y", interval="1d")
        wti = yf.download("CL=F", period="1y", interval="1d")
        
        if brent.empty or wti.empty:
            print("⚠️ Arbitrage Error: Failed to fetch underlying pair matrices.")
            return

        if isinstance(brent.columns, pd.MultiIndex): brent.columns = brent.columns.get_level_values(0)
        if isinstance(wti.columns, pd.MultiIndex): wti.columns = wti.columns.get_level_values(0)
        
        combined = pd.DataFrame(index=brent.index)
        combined["brent"] = brent["close"].astype(float)
        combined["wti"] = wti["close"].astype(float)
        combined = combined.ffill().bfill()
        
        combined["spread"] = combined["brent"] - combined["wti"]
        spread_arr = combined["spread"].to_numpy()
        
        upper_std, mid_std, lower_std = talib.BBANDS(spread_arr, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
        
        current_spread = float(combined["spread"].iloc[-1])
        prev_spread = float(combined["spread"].shift(1).iloc[-1])
        
        if current_spread > upper_std[-1] and prev_spread <= upper_std[-2]:
            sl, tp = get_risk_params("OIL_ARB_SPREAD", "SHORT_SPREAD", current_spread)
            supabase_client.table("signals").insert({
                "ticker": "BZ=F vs CL=F (Oil Spread)",
                "direction": "SHORT SPREAD (Sell Brent / Buy WTI)",
                "execution_price": current_spread,
                "stop_loss": sl,
                "take_profit": tp,
                "status": "PENDING"
            }).execute()
            print("🚨 ARBITRAGE SIGNAL: Overvalued crude oil spread dislocated upwards.")
            
        elif current_spread < lower_std[-1] and prev_spread >= lower_std[-2]:
            sl, tp = get_risk_params("OIL_ARB_SPREAD", "LONG_SPREAD", current_spread)
            supabase_client.table("signals").insert({
                "ticker": "BZ=F vs CL=F (Oil Spread)",
                "direction": "LONG SPREAD (Buy Brent / Sell WTI)",
                "execution_price": current_spread,
                "stop_loss": sl,
                "take_profit": tp,
                "status": "PENDING"
            }).execute()
            print("🚨 ARBITRAGE SIGNAL: Undervalued crude oil spread dislocated downwards.")
        else:
            print(f"🔍 Arbitrage tracking normal. Current spread: ${current_spread:.2f}")
            
    except Exception as e:
        print(f"❌ Statistical Arbitrage execution loop exception caught: {e}")

# ==============================================================================
# 🎛️ CORE RUNNER EXECUTIVE
# ==============================================================================
def run_pipeline():
    watch_list = [
        "EURUSD=X", "GBPUSD=X", "AUDUSD=X", "USDJPY=X", "USDCAD=X", 
        "^GSPC", "GC=F", "CL=F", "BZ=F"
    ]
    
    print(f"🏁 Launching Quantitative Cloud Scanner for {len(watch_list)} instruments...")
    
    # 🔍 SYSTEM VALIDATION: Verify if secrets are actually injecting into the container environment
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        print("🚨 CRITICAL PRE-BUILD ERROR: Supabase Credentials are missing from Container Env context!")
        print(f"DEBUG ENV DETECTED -> URL: {'PRESENT' if url else 'MISSING'}, KEY: {'PRESENT' if key else 'MISSING'}")
        sys.exit(1) # Kill the script explicitly to flag configuration errors instantly
        
    try:
        supabase = create_client(url, key)
        print("✅ Supabase client context initialized successfully inside container.")
    except Exception as connection_err:
        print(f"🚨 CRITICAL SYSTEM TERMINATION: DB initialization failed: {connection_err}")
        sys.exit(1)
    
    # Cycle 1: Process Asset-Specific Indicators
    for asset in watch_list:
        try:
            df = yf.download(asset, period="1y", interval="1d")
            if df.empty or len(df) < 200:
                print(f"⚠️ Skipping {asset}: Empty data or low depth.")
                continue
                
            if isinstance(df.columns, pd.MultiIndex): 
                df.columns = df.columns.get_level_values(0)
            df.columns = df.columns.str.lower()
            df = df.loc[~df.index.duplicated(keep="first")].sort_index().ffill().bfill()
            
            signal, trigger_price = execute_asset_strategy(asset, df)
            
            if signal:
                sl, tp = get_risk_params(asset, signal, trigger_price)
                supabase.table("signals").insert({
                    "ticker": asset,
                    "direction": signal,
                    "execution_price": trigger_price,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "status": "PENDING"
                }).execute()
                print(f"🚀 Found alpha trend entry configuration for {asset}. Data mapped to Cloud State.")
                
        except Exception as asset_err:
            print(f"❌ Processing exception triggered inside {asset} script nodes: {asset_err}")
            
    # Cycle 2: Execute Statistical Cross-Market Arbitrage Engine
    execute_statistical_arbitrage(supabase)
    print("🏆 Cloud execution framework completed safely.")

if __name__ == "__main__":
    run_pipeline()
