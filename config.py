# config.py

# 📅 SINGLE-ASSET WATCHLIST — S&P 500 only
WATCH_LIST = {
    "1d": ["^GSPC"],
}

# Volatility Multipliers for Dynamic ATR Target Allocations
RISK_PROFILES = {
    "^GSPC": {"sl": 2.0, "tp": 3.5},
    "DEFAULT": {"sl": 2.0, "tp": 3.5},
}

# 🔒 Enforce a minimum Reward:Risk ratio.
MIN_RR_RATIO = 1.5

# ⏱️ Deduplication window: how many bars back to look for a matching signal
DEDUP_LOOKBACK_BARS = {"1d": 5}

# 🕒 Session window (UTC) — kept for backward compatibility.
#    NOTE: scanner.py now interprets these hours as MARKET-LOCAL (US/Eastern)
#    via timeutils.to_market_tz(). For daily bars (0, 24) means "always open".
SESSION_WINDOWS = {
    "^GSPC": [(0, 24)],
}

# 🚦 ADX regime gate: trend strategies need ADX >= this value
ADX_TREND_THRESHOLD = 20.0

# 📉 VIX regime gate — only buy dips when VIX > this value AND falling
VIX_BUY_THRESHOLD = 18.0

# 📊 Multi-Timeframe Confirmation — weekly trend gate
MTF_ENABLED = True
MTF_WEEKLY_SMA_PERIOD = 30
MTF_MIN_WEEKLY_BARS = 30

# ⏱️ Outcome tracker settings
OUTCOME_MAX_AGE_DAYS = 45  # force-expire signals older than this

# 💰 Account sizing — used by sizing.py to compute units per signal
ACCOUNT_EQUITY = 10_000.0     # account currency
RISK_PER_TRADE_PCT = 1.0      # % of equity risked per trade

# Instrument specs: point_value = $ per 1.0 price move per unit
INSTRUMENT_SPECS = {
    "^GSPC": {"symbol": "SPY", "point_value": 1.0,  "type": "shares"},
    "SPY":   {"symbol": "SPY", "point_value": 1.0,  "type": "shares"},
    "ES=F":  {"symbol": "ES",  "point_value": 50.0, "type": "futures"},
}