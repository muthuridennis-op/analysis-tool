# strategies.py
import talib

def evaluate_forex(close_prices):
    ema_20 = talib.EMA(close_prices, timeperiod=20)
    df_ema_50 = talib.EMA(close_prices, timeperiod=50)
    rsi = talib.RSI(close_prices, timeperiod=14)
    
    cross_up = (ema_20 > df_ema_50) & (pd_shift(ema_20) <= pd_shift(df_ema_50))
    cross_down = (ema_20 < df_ema_50) & (pd_shift(ema_20) >= pd_shift(df_ema_50))
    
    if cross_up[-1] and (50 < rsi[-1] < 65): return "BUY"
    if cross_down[-1] and (35 < rsi[-1] < 50): return "SELL"
    return None

def evaluate_index(close_prices, sma_200):
    rsi_2 = talib.RSI(close_prices, timeperiod=2)
    if (close_prices[-1] > sma_200[-1]) and (rsi_2[-1] < 10): return "BUY"
    if (close_prices[-1] < sma_200[-1]) and (rsi_2[-1] > 90): return "SELL"
    return None

def evaluate_gold(close_prices, upper, lower, volume, volume_ma):
    break_up = (close_prices > upper) & (pd_shift(close_prices) <= pd_shift(upper))
    break_dn = (close_prices < lower) & (pd_shift(close_prices) >= pd_shift(lower))
    vol_ok = volume > volume_ma
    
    if break_up[-1] and vol_ok[-1]: return "BUY"
    if break_dn[-1] and vol_ok[-1]: return "SELL"
    return None

def evaluate_oil(macd, signal, volume, volume_ma):
    macd_up = (macd > signal) & (pd_shift(macd) <= pd_shift(signal))
    macd_dn = (macd < signal) & (pd_shift(macd) >= pd_shift(signal))
    vol_ok = volume > volume_ma
    
    if macd_up[-1] and vol_ok[-1]: return "BUY"
    if macd_dn[-1] and vol_ok[-1]: return "SELL"
    return None

def pd_shift(numpy_array):
    """Helper macro to mimic pandas shifting performance values safely"""
    import numpy as np
    return np.roll(numpy_array, 1)
