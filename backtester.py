# backtester.py
"""
Historical backtester for the S&P 500 RSI(2) + VIX + ADX + weekly MTF strategy.

Reuses strategies.evaluate_index() so the exact same rule that fires live
is the rule that gets validated here.
"""
import argparse
import os
import pandas as pd
import numpy as np
import talib
import yfinance as yf

import config
import strategies
from logger import get_logger

log = get_logger(__name__)


def load_history(ticker: str, start: str, end: str) -> pd.DataFrame:
    log.info("Downloading %s from %s to %s", ticker, start, end)
    df = yf.download(ticker, start=start, end=end, interval="1d", progress=False)
    if df.empty:
        raise RuntimeError(f"No data returned for {ticker}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = df.columns.str.lower()
    df = df.loc[~df.index.duplicated(keep="first")].sort_index().ffill().bfill()
    log.info("Loaded %d bars for %s (columns: %s)", len(df), ticker, list(df.columns))
    return df


def load_vix(start: str, end: str) -> pd.Series:
    try:
        vix = yf.download("^VIX", start=start, end=end, interval="1d", progress=False)
        if vix.empty:
            return pd.Series(dtype=float)
        if isinstance(vix.columns, pd.MultiIndex):
            vix.columns = vix.columns.get_level_values(0)
        vix.columns = vix.columns.str.lower()
        return vix["close"]
    except Exception as e:
        log.warning("VIX load failed: %s", e)
        return pd.Series(dtype=float)


def get_risk_bounds(ticker, signal, price, atr):
    if pd.isna(atr) or atr <= 0:
        atr = price * 0.015
    profile = config.RISK_PROFILES.get(ticker, config.RISK_PROFILES["DEFAULT"])
    risk = atr * profile["sl"]
    reward = atr * profile["tp"]
    min_rr = getattr(config, "MIN_RR_RATIO", 1.5)
    if reward / risk < min_rr:
        reward = risk * min_rr
    if signal == "BUY":
        return price - risk, price + reward
    return price + risk, price - reward


def simulate_trade(df, entry_idx, direction, sl, tp, max_hold_bars=30):
    """
    Walks forward bar-by-bar. Conservative fills:
      - If a bar gaps past SL/TP at open, fill at open.
      - If a bar's range spans both SL and TP intrabar, assume SL first.
    """
    end_idx = min(entry_idx + max_hold_bars, len(df) - 1)

    for i in range(entry_idx + 1, end_idx + 1):
        op = float(df["open"].iloc[i])
        hi = float(df["high"].iloc[i])
        lo = float(df["low"].iloc[i])

        if direction == "BUY":
            if op <= sl:
                return i, op, "SL_GAP"
            if op >= tp:
                return i, op, "TP_GAP"
            if lo <= sl:
                return i, sl, "SL"
            if hi >= tp:
                return i, tp, "TP"
        else:
            if op >= sl:
                return i, op, "SL_GAP"
            if op <= tp:
                return i, op, "TP_GAP"
            if hi >= sl:
                return i, sl, "SL"
            if lo <= tp:
                return i, tp, "TP"

    exit_price = float(df["close"].iloc[end_idx])
    return end_idx, exit_price, "TIME"


def run_backtest(ticker="^GSPC", start="2010-01-01", end=None, max_hold_bars=30):
    end = end or pd.Timestamp.utcnow().strftime("%Y-%m-%d")
    df = load_history(ticker, start, end)

    if len(df) < 220:
        raise RuntimeError(f"Need >=220 bars, got {len(df)}")

    vix_series = load_vix(start, end)
    if not vix_series.empty:
        vix_series = vix_series.reindex(df.index).ffill()
    else:
        vix_series = pd.Series([np.nan] * len(df), index=df.index)

    weekly_df = df.resample("W-FRI").agg({
        "open": "first", "high": "max",
        "low": "min", "close": "last", "volume": "sum"
    }).dropna()
    w_close = weekly_df["close"]
    w_sma = w_close.rolling(getattr(config, "MTF_WEEKLY_SMA_PERIOD", 30)).mean()

    cl = df["close"].to_numpy().astype(float)
    hi = df["high"].to_numpy().astype(float)
    lw = df["low"].to_numpy().astype(float)
    sma_200 = talib.SMA(cl, timeperiod=200)
    atr_series = talib.ATR(hi, lw, cl, timeperiod=14)

    trades = []
    warmup = 200
    i = warmup

    while i < len(df) - 1:
        cl_slice = cl[: i + 1]
        hi_slice = hi[: i + 1]
        lw_slice = lw[: i + 1]
        sma_slice = sma_200[: i + 1]

        vix_slice = vix_series.iloc[: i + 1].to_numpy() if not vix_series.empty else None

        current_date = df.index[i]
        wk_mask = w_close.index <= current_date
        wk_close_slice = w_close[wk_mask].to_numpy() if wk_mask.any() else None
        wk_sma_slice = w_sma[wk_mask].to_numpy() if wk_mask.any() else None

        signal = strategies.evaluate_index(
            cl_slice, sma_slice, vix_slice, hi_slice, lw_slice,
            weekly_close=wk_close_slice,
            weekly_sma=wk_sma_slice,
        )

        if signal is None:
            i += 1
            continue

        entry_price = float(cl[i])
        atr_val = float(atr_series[i]) if not np.isnan(atr_series[i]) else entry_price * 0.015
        sl, tp = get_risk_bounds(ticker, signal, entry_price, atr_val)

        exit_idx, exit_price, outcome = simulate_trade(
            df, i, signal, sl, tp, max_hold_bars=max_hold_bars
        )

        if signal == "BUY":
            pnl_pct = (exit_price - entry_price) / entry_price * 100.0
        else:
            pnl_pct = (entry_price - exit_price) / entry_price * 100.0

        trades.append({
            "entry_date": df.index[i],
            "exit_date": df.index[exit_idx],
            "direction": signal,
            "entry": entry_price,
            "exit": exit_price,
            "sl": sl,
            "tp": tp,
            "outcome": outcome,
            "bars_held": exit_idx - i,
            "pnl_pct": pnl_pct,
        })

        i = exit_idx + 1

    return pd.DataFrame(trades)


def compute_metrics(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"trades": 0}

    wins = trades[trades["pnl_pct"] > 0]
    losses = trades[trades["pnl_pct"] <= 0]

    total = len(trades)
    win_rate = len(wins) / total * 100.0
    avg_win = wins["pnl_pct"].mean() if not wins.empty else 0.0
    avg_loss = losses["pnl_pct"].mean() if not losses.empty else 0.0
    expectancy = trades["pnl_pct"].mean()

    gross_profit = wins["pnl_pct"].sum()
    gross_loss = abs(losses["pnl_pct"].sum())
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

    trades_sorted = trades.sort_values("entry_date").copy()
    trades_sorted["equity"] = (1 + trades_sorted["pnl_pct"] / 100.0).cumprod()

    peak = trades_sorted["equity"].cummax()
    dd = (trades_sorted["equity"] / peak - 1.0) * 100.0
    max_dd = dd.min()

    if trades["pnl_pct"].std() > 0:
        trades_per_year = 252 / max(trades["bars_held"].mean(), 1)
        sharpe = (expectancy / trades["pnl_pct"].std()) * np.sqrt(trades_per_year)
    else:
        sharpe = 0.0

    return {
        "trades": total,
        "win_rate": round(win_rate, 2),
        "avg_win_pct": round(avg_win, 3),
        "avg_loss_pct": round(avg_loss, 3),
        "expectancy_pct": round(expectancy, 3),
        "profit_factor": round(profit_factor, 2),
        "sharpe": round(sharpe, 2),
        "max_dd_pct": round(max_dd, 2),
        "avg_bars_held": round(trades["bars_held"].mean(), 1),
        "tp_hits": int(trades["outcome"].isin(["TP", "TP_GAP"]).sum()),
        "sl_hits": int(trades["outcome"].isin(["SL", "SL_GAP"]).sum()),
        "time_exits": int((trades["outcome"] == "TIME").sum()),
    }


def save_report(trades, metrics, out_dir="backtest_results"):
    os.makedirs(out_dir, exist_ok=True)
    ts = pd.Timestamp.utcnow().strftime("%Y%m%d_%H%M%S")

    trades_path = os.path.join(out_dir, f"trades_{ts}.csv")
    trades.to_csv(trades_path, index=False)

    report_path = os.path.join(out_dir, f"report_{ts}.txt")
    with open(report_path, "w") as f:
        f.write("=== S&P 500 Backtest Report ===\n")
        f.write(f"Generated: {pd.Timestamp.utcnow()}\n\n")
        for k, v in metrics.items():
            f.write(f"{k:>20}: {v}\n")

    log.info("Trades saved: %s", trades_path)
    log.info("Report saved: %s", report_path)
    return trades_path, report_path


def print_metrics(metrics: dict):
    print("\n" + "=" * 52)
    print("  S&P 500 BACKTEST RESULTS")
    print("=" * 52)
    for k, v in metrics.items():
        print(f"{k:>20}: {v}")
    print("=" * 52 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest S&P 500 RSI(2) strategy")
    parser.add_argument("--start", default="2010-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--hold", type=int, default=30, help="Max hold in bars")
    args = parser.parse_args()

    trades = run_backtest(start=args.start, end=args.end, max_hold_bars=args.hold)
    metrics = compute_metrics(trades)
    print_metrics(metrics)
    if not trades.empty:
        save_report(trades, metrics)