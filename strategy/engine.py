import json
import pandas as pd
from sqlalchemy import select
from strategy.models.signal import GeneratedSignal
from strategy.signal_validator import valid_frame
from strategy.strategies.ema_crossover import EMACrossoverStrategy

class StrategyEngine:
    def __init__(self, session): self.session = session; self.strategy = EMACrossoverStrategy()
    def evaluate(self, symbol, candles, config, source="SIMULATION"):
        def value(candle, key): return getattr(candle, key) if hasattr(candle, key) else candle[key]
        frame = pd.DataFrame([{k: value(candle, k) for k in ("open", "high", "low", "close", "volume")} for candle in candles], index=[value(candle, "timestamp") for candle in candles])
        if not valid_frame(frame, 2): return self.strategy.generate(symbol, frame, config, source)
        result = self.strategy.generate(symbol, frame, config, source)
        if result.action != "NO_TRADE": self.persist(result)
        return result
    def persist(self, signal):
        existing = self.session.scalar(select(GeneratedSignal).where(GeneratedSignal.symbol == signal.symbol, GeneratedSignal.candle_timestamp == signal.candle_timestamp, GeneratedSignal.strategy_name == signal.strategy_name))
        if existing: return existing
        item = GeneratedSignal(symbol=signal.symbol, action=signal.action, classification=signal.classification, score=signal.score, reference_price=signal.price, entry_price=signal.price, stop_loss=signal.stop_loss, target_price=signal.target_price, risk_reward=signal.risk_reward, strategy_name=signal.strategy_name, data_source=signal.source, candle_timestamp=signal.candle_timestamp, details_json=json.dumps({"indicators": signal.indicators, "confirmations": signal.confirmations}))
        self.session.add(item); self.session.flush(); return item
    def scan(self, symbol_candles: dict, config, source="SIMULATION"):
        results = {}
        for symbol, candles in symbol_candles.items():
            try: results[symbol] = self.evaluate(symbol, candles, config, source)
            except (ValueError, KeyError) as error: results[symbol] = {"error": str(error)}
        return results
