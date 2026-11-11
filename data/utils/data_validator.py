from datetime import datetime

VALID_TIMEFRAMES = {"1m", "3m", "5m", "15m", "30m", "1h", "1d"}
def validate_candle(candle: dict) -> None:
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    if not required.issubset(candle): raise ValueError("Candle fields are incomplete")
    if not isinstance(candle["timestamp"], datetime) or candle["timestamp"].tzinfo is None: raise ValueError("Candle timestamp must be timezone-aware")
    if min(candle["open"], candle["high"], candle["low"], candle["close"]) <= 0: raise ValueError("Candle prices must be positive")
    if candle["high"] < max(candle["open"], candle["close"]) or candle["low"] > min(candle["open"], candle["close"]): raise ValueError("Invalid OHLC range")
    if not isinstance(candle["volume"], int) or candle["volume"] < 0: raise ValueError("Candle volume must be a non-negative integer")
def validate_timeframe(timeframe: str) -> None:
    if timeframe not in VALID_TIMEFRAMES: raise ValueError(f"Unsupported timeframe: {timeframe}")
