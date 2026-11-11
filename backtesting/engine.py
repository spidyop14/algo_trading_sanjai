import json
from dataclasses import asdict, dataclass
from datetime import time
from zoneinfo import ZoneInfo
import pandas as pd
from sqlalchemy import select
from backtesting.analytics import performance_metrics
from backtesting.costs import IndianEquityCostCalculator, TransactionCostConfig
from backtesting.models import BacktestRun, BacktestTrade
from strategy.strategies.ema_crossover import EMACrossoverStrategy

IST = ZoneInfo("Asia/Kolkata")
@dataclass(frozen=True)
class BacktestConfig:
    symbols: list[str]; timeframe: str; initial_capital: float = 100000; allocation_pct: float = 20; position_sizing: str = "ALLOCATION"; intraday: bool = True; strategy_name: str = "EMA crossover"

class HistoricalBacktestEngine:
    def __init__(self, session, strategy_config, costs=TransactionCostConfig()): self.session, self.strategy_config, self.costs, self.strategy = session, strategy_config, IndianEquityCostCalculator(costs), EMACrossoverStrategy()
    def run(self, candles_by_symbol: dict[str, list], config: BacktestConfig, source: str = "HISTORICAL"):
        if source == "SIMULATION": raise ValueError("Historical backtests require imported historical data, not simulated candles")
        if not candles_by_symbol or not any(candles_by_symbol.values()): raise ValueError("No historical OHLCV data available. Import CSV data before running a backtest.")
        cash, trades, equity = config.initial_capital, [], []; positions = {}
        for symbol, candles in candles_by_symbol.items():
            rows = sorted([self._row(c) for c in candles], key=lambda x: x["timestamp"])
            if len(rows) < 2: continue
            for i in range(1, len(rows)):
                bar, next_bar = rows[i - 1], rows[i]
                if config.intraday and not self._in_session(next_bar["timestamp"]): continue
                frame = pd.DataFrame(rows[:i], index=[r["timestamp"] for r in rows[:i]])[["open", "high", "low", "close", "volume"]]
                signal = self.strategy.generate(symbol, frame, self.strategy_config, source)
                position = positions.get(symbol)
                if position:
                    exit_price, reason = self._exit_price(position, next_bar)
                    if exit_price is None and signal.action == "SELL": exit_price, reason = next_bar["open"], "SIGNAL_EXIT"
                    if exit_price is None and config.intraday and next_bar["timestamp"].astimezone(IST).time() >= time(15, 15): exit_price, reason = next_bar["open"], "INTRADAY_CLOSE"
                    if exit_price is not None:
                        trade = self._close(symbol, position, exit_price, next_bar["timestamp"], reason); cash += position["entry"] * position["qty"] + trade["net_pnl"]; trades.append(trade); positions.pop(symbol)
                elif signal.action == "BUY":
                    entry = self.costs.execution_price("BUY", next_bar["open"]); qty = int((cash * config.allocation_pct / 100) // entry)
                    if qty > 0 and entry * qty <= cash:
                        cash -= entry * qty; positions[symbol] = {"entry": entry, "qty": qty, "stop": signal.stop_loss, "target": signal.target_price, "time": next_bar["timestamp"]}
                value = cash + sum(p["qty"] * next_bar["close"] for p in positions.values())
                equity.append({"timestamp": next_bar["timestamp"], "equity": value})
        for symbol, position in list(positions.items()):
            last = sorted([self._row(c) for c in candles_by_symbol[symbol]], key=lambda x: x["timestamp"])[-1]; trade = self._close(symbol, position, last["close"], last["timestamp"], "END_OF_DATA"); cash += position["entry"] * position["qty"] + trade["net_pnl"]; trades.append(trade); equity.append({"timestamp": last["timestamp"], "equity": cash})
        metrics = performance_metrics(config.initial_capital, equity, trades); return self._persist(config, source, trades, equity, metrics)
    def _row(self, candle): return {key: getattr(candle, key) if hasattr(candle, key) else candle[key] for key in ("timestamp", "open", "high", "low", "close", "volume")}
    def _in_session(self, stamp):
        local = stamp.astimezone(IST); return local.weekday() < 5 and time(9, 15) <= local.time() <= time(15, 30)
    def _exit_price(self, position, bar):
        if bar["open"] <= position["stop"]: return bar["open"], "STOP_LOSS_GAP"
        if bar["low"] <= position["stop"]: return position["stop"], "STOP_LOSS"
        if bar["open"] >= position["target"]: return bar["open"], "TARGET_GAP"
        if bar["high"] >= position["target"]: return position["target"], "TARGET"
        return None, None
    def _close(self, symbol, position, raw_exit, stamp, reason):
        exit_price = self.costs.execution_price("SELL", raw_exit); gross = (exit_price - position["entry"]) * position["qty"]; charges = self.costs.charges(position["entry"] * position["qty"], exit_price * position["qty"]); minutes = (stamp - position["time"]).total_seconds() / 60
        return {"symbol": symbol, "strategy": self.strategy.name, "entry_time": position["time"], "exit_time": stamp, "entry_price": position["entry"], "exit_price": exit_price, "quantity": position["qty"], "gross_pnl": round(gross, 2), "charges": charges, "net_pnl": round(gross - charges, 2), "exit_reason": reason, "holding_minutes": minutes}
    def _persist(self, config, source, trades, equity, metrics):
        run = BacktestRun(strategy_name=config.strategy_name, symbols=",".join(config.symbols), timeframe=config.timeframe, start_date=str(equity[0]["timestamp"]) if equity else "", end_date=str(equity[-1]["timestamp"]) if equity else "", initial_capital=config.initial_capital, final_capital=metrics["final_capital"], data_source=source, assumptions_json=json.dumps({**asdict(config), "costs": self.costs.config.as_dict()}), metrics_json=json.dumps(metrics, default=str)); self.session.add(run); self.session.flush()
        for trade in trades: self.session.add(BacktestTrade(run_id=run.id, strategy_name=trade["strategy"], **{k: v for k, v in trade.items() if k != "strategy"}))
        self.session.flush(); return {"run": run, "trades": trades, "equity": equity, "metrics": metrics}
