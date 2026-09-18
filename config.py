# config.py

# Universal Portfolio Watchlist Matrix
WATCH_LIST = [
    "EURUSD=X", "GBPUSD=X", "AUDUSD=X", "USDJPY=X", "USDCAD=X", # Forex
    "^GSPC",                                                    # S&P 500 Index
    "GC=F",                                                     # Gold Futures
    "CL=F", "BZ=F"                                              # Energy Module
]

# Volatility Multipliers for Dynamic ATR Target Allocations
RISK_PROFILES = {
    "^GSPC": {"sl": 1.5, "tp": 3.5},
    "CL=F":  {"sl": 2.5, "tp": 5.5},
    "BZ=F":  {"sl": 2.5, "tp": 5.5},
    "GC=F":  {"sl": 2.0, "tp": 4.5},
    "DEFAULT": {"sl": 2.0, "tp": 5.0}  # Baseline applied to Forex
}
