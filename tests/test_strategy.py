from datetime import datetime, timedelta, timezone
import pandas as pd
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from backend.database.models import Base
from strategy.engine import StrategyEngine
from strategy.indicators import atr, ema, macd, rsi, vwap
from strategy.models.signal import GeneratedSignal
from strategy.models.strategy_config import StrategyConfiguration
from strategy.signal_generator import SignalScorer
from strategy.strategies.ema_crossover import EMACrossoverStrategy
from strategy.utils.calculations import crossover, risk_levels, trailing_stop
from strategy.signal_validator import stale


def frame(values, final_volume=5000):
    index = pd.date_range("2026-01-01", periods=len(values), freq="5min", tz="Asia/Kolkata")
    return pd.DataFrame({"open": values, "high": [v + 1 for v in values], "low": [v - 1 for v in values], "close": values, "volume": [1000] * (len(values) - 1) + [final_volume]}, index=index)

def config(**updates):
    values = dict(name="test", min_signal_score=0, volume_multiple=1.0, ema_fast=3, ema_slow=6, rsi_period=5, rsi_bullish=50, rsi_bearish=50, macd_fast=3, macd_slow=6, macd_signal=3, atr_period=5, atr_multiplier=1.5, risk_reward=2, stop_mode="ATR", fixed_stop_pct=1)
    values.update(updates); return StrategyConfiguration(**values)


def test_indicator_calculations_and_nan_warmup():
    close = list(range(1, 31)); high = [v + 1 for v in close]; low = [v - 1 for v in close]
    assert ema(close, 9).iloc[:8].isna().all()
    assert rsi(close, 14).iloc[-1] == 100
    assert atr(high, low, close, 14).iloc[-1] > 0
    assert vwap(high, low, close, [100] * 30).iloc[-1] > 0
    assert set(macd(close).columns) == {"macd", "macd_signal", "macd_histogram"}

def test_crossover_requires_actual_event():
    assert crossover(9, 10, 11, 10) == 1
    assert crossover(11, 10, 12, 10) == 0
    assert crossover(11, 10, 9, 10) == -1

def test_score_classification():
    scorer = SignalScorer()
    assert scorer.score({"ema": True, "rsi": True, "macd": True, "volume": True, "trend": True}) == 100
    assert scorer.classification(80) == "STRONG" and scorer.classification(65) == "MODERATE" and scorer.classification(64) == "NO_TRADE"

def test_atr_stops_targets_and_trailing_are_directional():
    assert risk_levels("BUY", 100, 2, 1.5, 2) == (97.0, 106.0, 2)
    assert risk_levels("SELL", 100, 2, 1.5, 2) == (103.0, 94.0, 2)
    assert trailing_stop("BUY", 95, 110, 2) == 107
    assert trailing_stop("SELL", 105, 90, 2) == 93

def test_buy_and_sell_conditions_and_no_lookahead():
    buy = frame([100] * 25 + [98, 96, 94, 92, 120])
    sell = frame([100] * 25 + [102, 104, 106, 108, 80])
    strategy = EMACrossoverStrategy()
    buy_signal = strategy.generate("RELIANCE", buy, config(), "SIMULATION")
    sell_signal = strategy.generate("RELIANCE", sell, config(), "SIMULATION")
    assert buy_signal.action == "BUY" and buy_signal.stop_loss < buy_signal.price < buy_signal.target_price
    assert sell_signal.action == "SELL" and sell_signal.target_price < sell_signal.price < sell_signal.stop_loss

def test_insufficient_data_and_duplicate_signal_prevention():
    engine_db = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine_db); session = sessionmaker(bind=engine_db)()
    strategy_engine = StrategyEngine(session)
    short_rows = [{**row.to_dict(), "timestamp": stamp} for stamp, row in frame([100] * 5).iterrows()]
    short = strategy_engine.evaluate("RELIANCE", short_rows, config())
    assert short.action == "NO_TRADE"
    candles = []
    full = frame([100] * 25 + [98, 96, 94, 92, 120])
    for stamp, row in full.iterrows(): candles.append({**row.to_dict(), "timestamp": stamp})
    first = strategy_engine.evaluate("RELIANCE", candles, config(), "SIMULATION")
    second = strategy_engine.evaluate("RELIANCE", candles, config(), "SIMULATION")
    assert first.action == "BUY" and second.action == "BUY"
    assert session.scalar(select(func.count(GeneratedSignal.id))) == 1

def test_multi_stock_scan_isolates_symbol_failures():
    engine_db = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine_db); session = sessionmaker(bind=engine_db)()
    result = StrategyEngine(session).scan({"RELIANCE": [{"timestamp": datetime.now(timezone.utc), "open": 1, "high": 2, "low": 1, "close": 2, "volume": 1}], "BROKEN": [{}]}, config())
    assert result["RELIANCE"].action == "NO_TRADE" and "error" in result["BROKEN"]

def test_stale_candle_detection():
    assert stale(datetime.now(timezone.utc) - timedelta(minutes=11), timedelta(minutes=10))
    assert not stale(datetime.now(timezone.utc), timedelta(minutes=10))
