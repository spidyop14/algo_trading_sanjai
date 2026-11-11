import pandas as pd


def _series(values): return pd.Series(values, dtype="float64")
def ema(close, period: int): return _series(close).ewm(span=period, adjust=False, min_periods=period).mean()
def rsi(close, period: int = 14):
    delta = _series(close).diff(); gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean(); avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    result = 100 - (100 / (1 + avg_gain / avg_loss.replace(0, float("nan"))))
    return result.mask((avg_loss == 0) & (avg_gain > 0), 100).mask((avg_gain == 0) & (avg_loss > 0), 0).mask((avg_gain == 0) & (avg_loss == 0), 50)
def macd(close, fast: int = 12, slow: int = 26, signal: int = 9):
    line = ema(close, fast) - ema(close, slow); signal_line = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "macd_signal": signal_line, "macd_histogram": line - signal_line})
def atr(high, low, close, period: int = 14):
    high, low, close = _series(high), _series(low), _series(close); previous = close.shift(1)
    true_range = pd.concat([high - low, (high - previous).abs(), (low - previous).abs()], axis=1).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
def vwap(high, low, close, volume):
    typical = (_series(high) + _series(low) + _series(close)) / 3; volume = _series(volume)
    return (typical * volume).cumsum() / volume.cumsum().replace(0, float("nan"))
def bollinger(close, period: int = 20, stddev: float = 2.0):
    values = _series(close); middle = values.rolling(period, min_periods=period).mean(); deviation = values.rolling(period, min_periods=period).std(ddof=0)
    return pd.DataFrame({"bb_middle": middle, "bb_upper": middle + stddev * deviation, "bb_lower": middle - stddev * deviation})
def relative_volume(volume, period: int = 20):
    values = _series(volume); average = values.rolling(period, min_periods=period).mean()
    return values / average.replace(0, float("nan")), average
