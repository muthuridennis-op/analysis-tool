import yfinance as yf
import pandas as pd
import numpy as np
import talib
import os
import sys
from supabase import create_client

# ==========================================================
# 🛡️ SYSTEM RISK PROFILER (VOLATILITY-ADAPTIVE ATR)
# ==========================================================
def get_atr_risk_params(ticker, signal_type, current_price, atr_value):
    if pd.isna(atr_value) or atr_value <= 0:
        atr_value = current_price * 0.015
        
    if ticker == "^GSPC":
        sl_multiplier = 1.5  
        tp_multiplier = 3.5  
    elif ticker in ["CL=F", "BZ=F", "OIL_ARB_SPREAD"]:
        sl_multiplier = 2.5  
        tp_multiplier = 5.5  
    elif ticker == "GC=F":
        sl_multiplier = 2.0  
        tp_multiplier = 4.5  
    else:
        sl_multiplier = 2.0  
        tp_multiplier = 5.0  

    risk_dist = atr_value * sl_multiplier
    reward_dist = atr_value * tp_multiplier

    if signal_type == "BUY" or signal_type == "LONG_SPREAD":
        sl_price = current_price - risk_dist
        tp_price = current_price + reward_dist
    else:
        sl_price = current_price + risk_dist
        tp_price = current_price - reward_dist
        
    return float(sl_price), float(tp_price)

# ==========================================================
# 📊 TECHNICAL STRATEGY ENGINES
# ==========================================================
def execute_asset_strategy(ticker, df):
    close_prices = df["close"].to_numpy().astype(float)
    volume_data = df["volume"].to_numpy().astype(float)
    current_price = float(df["close"].iloc[-1])
    
    if ticker in ["EURUSD=X", "GBPUSD=X", "AUDUSD=X", "USDJPY=X", "USDCAD=X"]:
        df["ema_20"] = talib.EMA(close_prices, timeperiod=20)
        df["ema_50"] = talib.EMA(close_prices, timeperiod=50)
        df["rsi"] = talib.RSI(close_prices, timeperiod=14)
        
        cross_up = (df["ema_20"] > df["ema_50"]) & (df["ema_20"].shift(1) <= df["ema_50"].shift(1))
        cross_down = (df["ema_20"] < df["ema_50"]) & (df["ema_20"].shift(1) >= df["ema_50"].shift(1))
        
        if cross_up.iloc[-1] and (50 < df["rsi"].iloc[-1] < 65):
            return "BUY", current_price
        elif cross_down.iloc[-1] and (35 < df["rsi"].iloc[-1] < 50):
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
        up, mid, lw = talib.BBANDS(close_prices, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
        
        break_up = (df["close"] > up) & (df["close"].shift(1) <= up.shift(1))
        break_dn = (df["close"] < lw) & (df["close"].shift(1) >= lw.shift(1))
        vol_ok = df["volume"] > df["volume_ma"]
        
        if break_up.iloc[-1] and vol_ok.iloc[-1]:
            return "BUY", current_price
        elif break_dn.iloc[-1] and vol_ok.iloc[-1]:
            return "SELL", current_price

    elif ticker in ["CL=F", "BZ=F"]:
        df["volume_ma"] = talib.SMA(volume_data, timeperiod=20)
        macd, signal, hist = talib.MACD(close_prices, fastperiod=12, slowperiod=26, signalperiod=9)
        
        macd_up = (macd > signal) & (macd.shift(1) <= signal.shift(1))
        macd_dn = (macd < signal) & (macd.shift(1) >= signal.shift(1))
        vol_ok = df["volume"] > df["volume_ma"]
        
        if macd_up.iloc[-1] and vol_ok.iloc[-1]:
            return "BUY", current_price
        elif macd_dn.iloc[-1] and vol_ok.iloc[-1]:
            return "SELL", current_price

    return None, None

# ==========================================================
# ⛓️ STATISTICAL ARBITRAGE ENGINE (PAIRS)
# ==========================================================
def execute_statistical_arbitrage(supabase_client):
    print("⛓️ Running Arbitrage Engine...")
    try:
        brent = yf.download("BZ=F", period="1y", interval="1d")
        wti = yf.download("CL=F", period="1y", interval="1d")
        
        if brent.empty or wti.empty:
            print("⚠️ Pairs data missing.")
            return

        if isinstance(brent.columns, pd.MultiIndex):
            brent.columns = brent.columns.get_level_values(0)
        if isinstance(wti.columns, pd.MultiIndex):
            wti.columns = wti.columns.get_level_values(0)
        
        comb = pd.DataFrame(index=brent.index)
        comb["brent"] = brent["close"].astype(float)
        comb["wti"] = wti["close"].astype(float)
        comb = comb.ffill().bfill()
        
        comb["spread"] = comb["brent"] - comb["wti"]
        spread_arr = comb["spread"].to_numpy()
        
        up, mid, lw = talib.BBANDS(spread_arr, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
        
        cur_spread = float(comb["spread"].iloc[-1])
        prev_spread = float(comb["spread"].shift(1).iloc[-1])
        
        hi_spread = comb["spread"].rolling(14).max().to_numpy()
        lo_spread = comb["spread"].rolling(14).min().to_numpy()
        sp_atr = np.mean(hi_spread - lo_spread) / 2.0
        
        if cur_spread > up[-1] and prev_spread <= up[-2]:
            sl, tp = get_atr_risk_params("OIL_ARB_SPREAD", "SHORT_SPREAD", cur_spread, sp_atr)
            supabase_client.table("signals").insert({
                "ticker": "BZ=F vs CL=F (Spread)",
                "direction": "SHORT SPREAD (Sell Brent / Buy WTI)",
                "execution_price": cur_spread,
                "stop_loss": sl,
                "take_profit": tp,
                "status": "PENDING"
            }).execute()
            print("🚨 ARBITRAGE: Spread overvalued. Pushed to app.")
            
        elif cur_spread < lw[-1] and prev_spread >= lw[-2]:
            sl, tp = get_atr_risk_params("OIL_ARB_SPREAD", "LONG_SPREAD", cur_spread, sp_atr)
            supabase_client.table("signals").insert({
                "ticker": "BZ=F vs CL=F (Spread)",
                "direction": "LONG SPREAD (Buy Brent / Sell WTI)",
                "execution_price": cur_spread,
                "stop_loss": sl,
                "take_profit": tp,
                "status": "PENDING"
            }).execute()
            print("🚨 ARBITRAGE: Spread undervalued. Pushed to app.")
        else:
            print(f"🔍 Spread normal: ${cur_spread:.2f}")
            
    except Exception as e:
        print(f"❌ Arbitrage error: {e}")

# ==========================================================
# 🎛️ CORE RUNNER EXECUTIVE
# ==========================================================
def run_pipeline():
    watch_list = [
        "EURUSD=X", "GBPUSD=X", "AUDUSD=X", "USDJPY=X", "USDCAD=X", 
        "^GSPC", "GC=F", "CL=F", "BZ=F"
    ]
    
    print("🏁 Starting Cloud Scanner...")
    
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        print("🚨 CRITICAL ERROR: Env secrets are missing!")
        sys.exit(1)
        
    try:
        supabase = create_client(url, key)
        print("✅ DB Client loaded.")
    except Exception as conn_err:
        print(f"🚨 DB init failed: {conn_err}")
        sys.exit(1)
    
    # Cycle 1: Process individual assets
    for asset in watch_list:
        try:
            df = yf.download(asset, period="1y", interval="1d")
            if df.empty or len(df) < 200:
                print(f"⚠️ Skipping {asset}: Low data.")
                continue
                
            if isinstance(df.columns, pd.MultiIndex): 
                df.columns = df.columns.get_level_values(0)
            df.columns = df.columns.str.lower()
            df = df.loc[~df.index.duplicated(keep="first")].sort_index().ffill().bfill()
            
            hi = df["high"].to_numpy().astype(float)
            lw = df["low"].to_numpy().astype(float)
            cl = df["close"].to_numpy().astype(float)
            
            df["atr"] = talib.ATR(hi, lw, cl, timeperiod=14)
            current_atr = float(df["atr"].iloc[-1])
            
            signal, trigger_price = execute_asset_strategy(asset, df)
            
            if signal:
                sl, tp = get_atr_risk_params(asset, signal, trigger_price, current_atr)
                supabase.table("signals").insert({
                    "ticker": asset,
                    "direction": signal,
                    "execution_price": trigger_price,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "status": "PENDING"
                }).execute()
                print(f"🚀 Signal logged for {asset}.")
                
        except Exception as asset_err:
            print(f"❌ Error on asset {asset}: {asset_err}")
            
    # Cycle 2: Process Statistical Arbitrage
    execute_statistical_arbitrage(supabase)
    print("🏆 Pipeline loop completed safely.")

if __name__ == "__main__":
    run_pipeline()
