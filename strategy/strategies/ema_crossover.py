import pandas as pd
from strategy.indicators import atr, ema, macd, relative_volume, rsi, vwap
from strategy.signal_generator import Signal, SignalScorer
from strategy.utils.calculations import crossover, risk_levels


class EMACrossoverStrategy:
    name = "EMA crossover"
    def generate(self, symbol: str, frame: pd.DataFrame, config, source: str) -> Signal:
        minimum = max(config.ema_slow + 1, config.macd_slow + config.macd_signal, config.rsi_period + 1, config.atr_period + 1, 20)
        if len(frame) < minimum: return Signal(symbol, "NO_TRADE", "NO_TRADE", 0, 0, None, None, None, self.name, source, frame.index[-1] if len(frame) else None, {}, {"reason": "Insufficient historical candles"})
        close, high, low, volume = frame["close"], frame["high"], frame["low"], frame["volume"]
        fast, slow = ema(close, config.ema_fast), ema(close, config.ema_slow); rsi_values = rsi(close, config.rsi_period); macd_values = macd(close, config.macd_fast, config.macd_slow, config.macd_signal); atr_values = atr(high, low, close, config.atr_period); rel_volume, average_volume = relative_volume(volume)
        latest, prior = frame.index[-1], frame.index[-2]; direction = crossover(fast.loc[prior], slow.loc[prior], fast.loc[latest], slow.loc[latest])
        price = float(close.loc[latest]); bullish = direction == 1; bearish = direction == -1
        confirmations = {"ema": direction != 0, "rsi": bool(rsi_values.loc[latest] >= config.rsi_bullish if bullish else rsi_values.loc[latest] <= config.rsi_bearish if bearish else False), "macd": bool(macd_values.loc[latest, "macd"] > macd_values.loc[latest, "macd_signal"] if bullish else macd_values.loc[latest, "macd"] < macd_values.loc[latest, "macd_signal"] if bearish else False), "volume": bool(rel_volume.loc[latest] >= config.volume_multiple), "trend": bool(price > vwap(high, low, close, volume).loc[latest] if bullish else price < vwap(high, low, close, volume).loc[latest] if bearish else False)}
        scorer = SignalScorer(); score = scorer.score(confirmations); action = "BUY" if bullish else "SELL" if bearish else "NO_TRADE"; classification = scorer.classification(score)
        if classification == "NO_TRADE" or score < config.min_signal_score: action, classification = "NO_TRADE", "NO_TRADE"
        stop = target = rr = None
        if action != "NO_TRADE": stop, target, rr = risk_levels(action, price, float(atr_values.loc[latest]), config.atr_multiplier, config.risk_reward, config.stop_mode, config.fixed_stop_pct)
        indicators = {"ema_fast": float(fast.loc[latest]), "ema_slow": float(slow.loc[latest]), "rsi": float(rsi_values.loc[latest]), "macd": float(macd_values.loc[latest, "macd"]), "macd_signal": float(macd_values.loc[latest, "macd_signal"]), "atr": float(atr_values.loc[latest]), "relative_volume": float(rel_volume.loc[latest]), "average_volume": float(average_volume.loc[latest])}
        return Signal(symbol, action, classification, score, price, stop, target, rr, self.name, source, latest, indicators, confirmations)
