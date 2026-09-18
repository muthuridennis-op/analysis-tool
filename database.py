# database.py
import os
import sys
from supabase import create_client

class DatabaseManager:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        
        if not url or not key:
            print("🚨 CRITICAL ERROR: Database credentials missing from environment.")
            sys.exit(1)
            
        try:
            self.client = create_client(url, key)
            print("✅ Database client layer initialized securely.")
        except Exception as e:
            print(f"🚨 Connection initialization failed: {e}")
            sys.exit(1)

    def insert_signal(self, ticker, direction, price, sl, tp):
        """Inserts an active pending trade alert row past your RLS framework"""
        try:
            payload = {
                "ticker": ticker,
                "direction": direction,
                "execution_price": float(price),
                "stop_loss": float(sl),
                "take_profit": float(tp),
                "status": "PENDING"
            }
            self.client.table("signals").insert(payload).execute()
            print(f"🚀 Signal uploaded successfully for {ticker}.")
        except Exception as error:
            print(f"❌ Failed to commit data row to cloud: {error}")
