# strategies.py
import talib
import numpy as np

from logger import get_logger

log = get_logger(__name__)


def safe_shift(numpy_array):
    """
    Safely shifts numeric values by 1 candle back.
    Replaces np.roll to prevent the oldest historical data point
    from rolling over to index position [-1].
    """
    result = np.empty_like(numpy_array)
    result[0] = np.nan
    result[1:] = numpy_array[:-1]
    return result


def evaluate_index(close_prices, sma_200, vix_series=None, high=None, low=None,
                   weekly_close=None, weekly_sma=None):
    """
    RSI(2) mean-reversion with SMA(200) trend filter for the S&P 500.

    Filters applied:
      - Long-only dips above the 200-day SMA (single-timeframe trend)
      - Multi-timeframe gate: weekly trend must agree with daily signal
      - Optional VIX gate: only BUY when VIX > threshold AND falling
      - Optional ADX gate: only fire when market is trending (ADX >= 20)

    Args:
        close_prices:  daily closes (np.array)
        sma_200:       daily SMA(200) array
        vix_series:    optional daily VIX closes (np.array), most recent last
        high, low:     daily high/low arrays for ADX
        weekly_close:  weekly closes (np.array)
        weekly_sma:    weekly SMA (np.array)

    Returns: "BUY", "SELL", or None
    """
    if close_prices is None or len(close_prices) < 200:
        log.debug("Insufficient daily bars (%s)",
                  len(close_prices) if close_prices is not None else 0)
        return None

    rsi_2 = talib.RSI(close_prices, timeperiod=2)
    if np.isnan(rsi_2[-1]) or np.isnan(sma_200[-1]):
        log.debug("RSI(2) or SMA(200) is NaN — skipping.")
        return None

    # --- Multi-timeframe gate (weekly trend) ---
    weekly_bull = None
    weekly_bear = None
    if weekly_close is not None and weekly_sma is not None and len(weekly_close) >= 1:
        if not np.isnan(weekly_sma[-1]):
            weekly_bull = weekly_close[-1] > weekly_sma[-1]
            weekly_bear = weekly_close[-1] < weekly_sma[-1]
            log.debug("Weekly MTF gate: weekly_close=%.2f weekly_sma=%.2f bull=%s",
                      weekly_close[-1], weekly_sma[-1], weekly_bull)

    # --- VIX filter (BUY side only) ---
    vix_ok_buy = True
    if vix_series is not None and len(vix_series) >= 2:
        if not (np.isnan(vix_series[-1]) or np.isnan(vix_series[-2])):
            from config import VIX_BUY_THRESHOLD
            vix_ok_buy = (vix_series[-1] > VIX_BUY_THRESHOLD) and (vix_series[-1] < vix_series[-2])
            log.debug("VIX gate: value=%.2f prev=%.2f ok=%s",
                      vix_series[-1], vix_series[-2], vix_ok_buy)
        else:
            log.debug("VIX gate skipped: NaN in tail")

    # --- ADX regime gate ---
    adx_ok = True
    if high is not None and low is not None:
        try:
            adx = talib.ADX(high, low, close_prices, timeperiod=14)
            val = adx[-1]
            if not np.isnan(val):
                from config import ADX_TREND_THRESHOLD
                adx_ok = val >= ADX_TREND_THRESHOLD
                log.debug("ADX gate: value=%.2f ok=%s", val, adx_ok)
        except Exception as e:
            log.warning("ADX calculation failed: %s", e)
            adx_ok = True

    # --- Daily signal logic ---
    above_trend = close_prices[-1] > sma_200[-1]
    below_trend = close_prices[-1] < sma_200[-1]

    log.debug("Eval: close=%.2f sma200=%.2f rsi2=%.2f above_trend=%s",
              close_prices[-1], sma_200[-1], rsi_2[-1], above_trend)

    # BUY: daily uptrend + RSI dip + VIX elevated + ADX trending + weekly bull
    if above_trend and rsi_2[-1] < 20 and vix_ok_buy and adx_ok:
        if weekly_bull is False:
            log.info("BUY skipped: weekly trend is bearish (MTF veto). rsi2=%.2f",
                     rsi_2[-1])
            return None
        log.info("BUY triggered (rsi2=%.2f vix_ok=%s adx_ok=%s weekly_bull=%s)",
                 rsi_2[-1], vix_ok_buy, adx_ok, weekly_bull)
        return "BUY"

    # SELL: daily downtrend + RSI overbought + weekly bear
    if below_trend and rsi_2[-1] > 80:
        if weekly_bear is False:
            log.info("SELL skipped: weekly trend is bullish (MTF veto). rsi2=%.2f",
                     rsi_2[-1])
            return None
        log.info("SELL triggered (rsi2=%.2f weekly_bear=%s)",
                 rsi_2[-1], weekly_bear)
        return "SELL"

    return None