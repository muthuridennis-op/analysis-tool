import yfinance as yf
import pandas as pd
import numpy as np
import talib
import os
import requests
from supabase import create_client

def push_telegram_alert(message):
    """Fires an instant direct notification to your Telegram application"""
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        url = f"https://telegram.org{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, json=payload, timeout=10)
            print("✉️ Telegram notification broadcast completed successfully.")
        except Exception as e:
            print(f"⚠️ Telegram failure: {e}")

def push_discord_alert(message):
    """Fires a stylized rich text webhook embed directly to your Discord channel"""
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if webhook_url:
        payload = {
            "username": "Algo Signal Engine",
            "content": f"🚨 **NEW TRADING SIGNAL IDENTIFIED** 🚨\n{message}"
        }
        try:
            requests.post(webhook_url, json=payload, timeout=10)
            print("✉️ Discord channel webhook broadcast completed successfully.")
        except Exception as e:
            print(f"⚠️ Discord failure: {e}")

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
            current_vol = float(df["volume"].iloc[-1])
            avg_vol = float(df["volume_ma"].iloc[-1])
            
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
            
            # --- NOTIFICATION FRAMEWORK ---
            # Replace the placeholder URL below with your real Streamlit App URL link
            dashboard_url = "https://streamlit.app" 
            
            alert_msg = (
                f"📈 *Asset:* {ticker}\n"
                f"⚡ *Direction:* {signal_type}\n"
                f"💵 *Trigger Price:* ${current_price:.4f}\n"
                f"🛡️ *Stop Loss:* ${sl_price:.4f} | 🎯 *Take Profit:* ${tp_price:.4f}\n"
                f"📊 *Volume Profile:* Strong (Current: {current_vol:,.0f} > 20MA: {avg_vol:,.0f})\n\n"
                f"👉 Open dashboard to act: {dashboard_url}"
            )
            
            push_telegram_alert(alert_msg)
            push_discord_alert(alert_msg)
        else:
            print("🔍 Crossover spotted, but REJECTED due to low institutional volume (Sideways Market).")
    else:
        print("🔍 Scanning Complete: No structural technical patterns registered on this bar.")

if __name__ == "__main__":
    run_pipeline()
