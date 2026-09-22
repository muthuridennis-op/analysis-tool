# timeutils.py
"""
Central timezone helpers. All internal timestamps are UTC-aware.

Why this exists:
  - yfinance returns naive daily-bar indexes (calendar dates)
  - Supabase returns UTC ISO strings
  - Mixing naive and aware timestamps causes silent comparison bugs
  - Market hours are America/New_York, but we store/compare in UTC

Rule: any timestamp entering the system gets coerced to tz-aware UTC.
      Only convert to market-local for display or session-window checks.
"""
import pandas as pd

MARKET_TZ = "America/New_York"


def utcnow() -> pd.Timestamp:
    """Always return a tz-aware UTC timestamp."""
    return pd.Timestamp.now(tz="UTC")


def to_utc(ts) -> pd.Timestamp:
    """Coerce any timestamp to tz-aware UTC.

    Naive timestamps are assumed to be market-local dates (yfinance daily
    bars) and anchored at market close (16:00 ET).
    """
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize(MARKET_TZ, nonexistent="shift_forward", ambiguous="NaT")
        if t is pd.NaT:
            # Fallback if localization failed (e.g. DST edge) — assume UTC
            t = pd.Timestamp(ts).tz_localize("UTC")
        else:
            t = t.tz_convert("UTC")
    return t


def to_market_tz(ts) -> pd.Timestamp:
    """Convert any timestamp to US/Eastern (for session-window logic)."""
    return to_utc(ts).tz_convert(MARKET_TZ)


def daily_index_to_utc(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Normalize a naive daily-bar index to UTC-aware timestamps."""
    return pd.DatetimeIndex([to_utc(d) for d in idx])