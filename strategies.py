# strategies.py
import talib
import numpy as np

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

def evaluate_forex(close_prices):
    ema_20 = talib.EMA(close_prices, timeperiod=20)
    ema_50 = talib.EMA(close_prices, timeperiod=50)
    rsi = talib.RSI(close_prices, timeperiod=14)
    
    prev_ema_20 = safe_shift(ema_20)
    prev_ema_50 = safe_shift(ema_50)
    
    cross_up = (ema_20 > ema_50) & (prev_ema_20 <= prev_ema_50)
    cross_down = (ema_20 < ema_50) & (prev_ema_20 >= prev_ema_50)
    
    if cross_up[-1] and (50 < rsi[-1] < 65): return "BUY"
    if cross_down[-1] and (35 < rsi[-1] < 50): return "SELL"
    return None

def evaluate_index(close_prices, sma_200):
    rsi_2 = talib.RSI(close_prices, timeperiod=2)
    if (close_prices[-1] > sma_200[-1]) and (rsi_2[-1] < 10): return "BUY"
    if (close_prices[-1] < sma_200[-1]) and (rsi_2[-1] > 90): return "SELL"
    return None

def evaluate_gold(close_prices, upper, lower, volume, volume_ma):
    prev_close = safe_shift(close_prices)
    prev_upper = safe_shift(upper)
    prev_lower = safe_shift(lower)
    
    break_up = (close_prices > upper) & (prev_close <= prev_upper)
    break_dn = (close_prices < lower) & (prev_close >= prev_lower)
    vol_ok = volume > volume_ma
    
    if break_up[-1] and vol_ok[-1]: return "BUY"
    if break_dn[-1] and vol_ok[-1]: return "SELL"
    return None

def evaluate_oil(macd, signal, volume, volume_ma):
    prev_macd = safe_shift(macd)
    prev_signal = safe_shift(signal)
    
    macd_up = (macd > signal) & (prev_macd <= prev_signal)
    macd_dn = (macd < signal) & (prev_macd >= prev_signal)
    vol_ok = volume > volume_ma
    
    if macd_up[-1] and vol_ok[-1]: return "BUY"
    if macd_dn[-1] and vol_ok[-1]: return "SELL"
    return None
