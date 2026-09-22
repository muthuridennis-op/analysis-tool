# sizing.py
"""
Position sizing helpers — single source of truth for scanner + dashboard.

Reads account equity and risk % from config, looks up the instrument spec,
and returns units to trade so that max loss at the stop == risk_cash.
"""
import config


def compute_position_size(ticker: str, entry: float, stop: float):
    """
    Returns dict:
        {
          "units": float,          # shares (int) or contracts (float)
          "risk_cash": float,      # $ at risk
          "risk_per_unit": float,  # $ per 1 unit at the stop
          "instrument": str,       # e.g. "SPY" or "ES"
          "type": str,             # "shares" | "futures"
        }
    or None if sizing is impossible.
    """
    spec = config.INSTRUMENT_SPECS.get(ticker)
    if spec is None:
        return None

    risk_per_unit = abs(entry - stop) * spec["point_value"]
    if risk_per_unit <= 0:
        return None

    risk_cash = config.ACCOUNT_EQUITY * (config.RISK_PER_TRADE_PCT / 100.0)
    units = risk_cash / risk_per_unit

    if spec["type"] == "shares":
        units = int(units)  # whole shares
    else:
        units = round(units, 2)  # fractional contracts

    if units <= 0:
        return None

    return {
        "units": units,
        "risk_cash": round(risk_cash, 2),
        "risk_per_unit": round(risk_per_unit, 4),
        "instrument": spec["symbol"],
        "type": spec["type"],
    }