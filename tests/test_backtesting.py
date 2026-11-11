from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from backend.database.models import Base
from backtesting.costs import IndianEquityCostCalculator, TransactionCostConfig
from backtesting.engine import BacktestConfig, HistoricalBacktestEngine
from backtesting.models import BacktestRun, BacktestTrade
from backtesting.export import trade_ledger_csv
from strategy.models.strategy_config import StrategyConfiguration
from strategy.signal_generator import Signal

IST = ZoneInfo("Asia/Kolkata")
def bars(prices):
    start = datetime(2026, 1, 5, 9, 15, tzinfo=IST)
    return [{"timestamp": start + timedelta(minutes=5*i), "open": price, "high": price + 1, "low": price - 1, "close": price, "volume": 1000} for i, price in enumerate(prices)]
class BuyThenHold:
    name = "Test strategy"
    def __init__(self): self.calls = 0
    def generate(self, symbol, frame, config, source):
        self.calls += 1; stamp = frame.index[-1]
        if self.calls == 1: return Signal(symbol, "BUY", "STRONG", 100, float(frame.close.iloc[-1]), 95, 110, 2, self.name, source, stamp, {}, {})
        return Signal(symbol, "NO_TRADE", "NO_TRADE", 0, float(frame.close.iloc[-1]), None, None, None, self.name, source, stamp, {}, {})

@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine); db = sessionmaker(bind=engine)(); yield db; db.close()

def runner(session):
    r = HistoricalBacktestEngine(session, StrategyConfiguration(name="test", ema_slow=2, macd_slow=2, macd_signal=1, rsi_period=2, atr_period=2)); r.strategy = BuyThenHold(); return r

def test_costs_are_configurable_and_slippage_directional():
    calc = IndianEquityCostCalculator(TransactionCostConfig(brokerage_pct=.1, stt_pct=.1, slippage_pct=.1))
    assert calc.execution_price("BUY", 100) == pytest.approx(100.1)
    assert calc.execution_price("SELL", 100) == pytest.approx(99.9)
    assert calc.charges(1000, 1100) > 0

def test_historical_backtest_next_bar_stop_and_persistence(session):
    result = runner(session).run({"RELIANCE": bars([100, 100, 94, 94])}, BacktestConfig(["RELIANCE"], "5m", allocation_pct=10), "HISTORICAL")
    assert len(result["trades"]) == 1 and result["trades"][0]["exit_reason"] == "STOP_LOSS_GAP"
    assert session.scalar(select(BacktestRun)) is not None and session.scalar(select(BacktestTrade)) is not None

def test_target_execution_and_no_lookahead(session):
    result = runner(session).run({"RELIANCE": bars([100, 100, 111, 111])}, BacktestConfig(["RELIANCE"], "5m"), "HISTORICAL")
    trade = result["trades"][0]
    assert trade["entry_time"] > bars([100])[0]["timestamp"] and trade["exit_reason"] == "TARGET_GAP"

def test_no_data_and_simulation_are_rejected(session):
    with pytest.raises(ValueError, match="No historical"):
        runner(session).run({}, BacktestConfig([], "1d"), "HISTORICAL")
    with pytest.raises(ValueError, match="historical"):
        runner(session).run({"RELIANCE": bars([100, 100])}, BacktestConfig(["RELIANCE"], "5m"), "SIMULATION")

def test_no_trade_metrics_and_csv_compatible_ledger(session):
    class NoTrade(BuyThenHold):
        def generate(self, symbol, frame, config, source): return Signal(symbol, "NO_TRADE", "NO_TRADE", 0, 100, None, None, None, self.name, source, frame.index[-1], {}, {})
    r = runner(session); r.strategy = NoTrade(); result = r.run({"RELIANCE": bars([100, 101, 102])}, BacktestConfig(["RELIANCE"], "5m"), "HISTORICAL")
    assert result["metrics"]["total_trades"] == 0 and result["metrics"]["win_rate"] is None

def test_csv_export_has_trade_ledger_headers():
    output = trade_ledger_csv([{ "symbol": "RELIANCE", "strategy": "EMA crossover", "entry_time": "a", "exit_time": "b", "entry_price": 1, "exit_price": 2, "quantity": 1, "gross_pnl": 1, "charges": 0, "net_pnl": 1, "exit_reason": "TARGET", "holding_minutes": 5 }]).decode()
    assert output.startswith("symbol,strategy,entry_time") and "RELIANCE" in output
