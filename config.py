# config.py

# 📅 MULTI-TIMEFRAME WATCHLIST MATRIX
# Maps assets to their ideal scanning time horizons.
# Valid yfinance intervals: "1d" (Daily), "4h" (4-Hour)
WATCH_LIST = {
    "1d": [
        "^GSPC",                  # S&P 500 Index (Mean-Reversion)
        "GC=F",                   # Gold Futures (BB Breakout)
        "CL=F", "BZ=F"            # Oil Futures (MACD Momentum)
    ],
    "4h": [
        "EURUSD=X", "GBPUSD=X",   # Fast-moving Forex Swing trading
        "AUDUSD=X", "USDJPY=X", 
        "USDCAD=X"
    ]
}

# Volatility Multipliers for Dynamic ATR Target Allocations
RISK_PROFILES = {
    "^GSPC": {"sl": 1.5, "tp": 3.5},
    "CL=F":  {"sl": 2.5, "tp": 5.5},
    "BZ=F":  {"sl": 2.5, "tp": 5.5},
    "GC=F":  {"sl": 2.0, "tp": 4.5},
    "DEFAULT": {"sl": 2.0, "tp": 5.0}  # Applied to Forex assets
}
