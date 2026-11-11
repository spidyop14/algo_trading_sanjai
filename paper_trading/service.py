from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select
from backend.core.exceptions import RiskViolation
from backend.database.models import OrderSide, OrderType, Position, TradeHistory
from backend.database.repositories import get_or_create_paper_account
from backend.providers.base_provider import Quote as LegacyQuote
from backend.trading.order_manager import OrderManager
from backend.trading.portfolio_manager import PortfolioManager
from data.providers.base_provider import ProviderUnavailable
from paper_trading.models import PaperExecution, PaperNotification, PaperPositionControl, PaperRiskControl, PaperTradingSession, PortfolioSnapshot
from backend.schemas.orders import OrderRequest
from strategy.engine import StrategyEngine
from strategy.strategy_manager import StrategyManager


class _PaperQuoteAdapter:
    def __init__(self, provider): self.provider = provider
    def quote(self, symbol):
        quote = self.provider.quote(symbol)
        return LegacyQuote(symbol=quote.symbol, price=quote.ltp, change_percent=quote.change_percent, volume=quote.volume, simulated=not quote.is_live)

class PaperTradingService:
    def __init__(self, session, provider): self.session, self.provider, self.adapter = session, provider, _PaperQuoteAdapter(provider)
    def account(self): return get_or_create_paper_account(self.session)
    def _control(self, account):
        control = self.session.get(PaperRiskControl, account.id)
        if not control: control = PaperRiskControl(account_id=account.id); self.session.add(control); self.session.flush()
        return control
    def state(self):
        account = self.account(); trading = self.session.scalar(select(PaperTradingSession).where(PaperTradingSession.account_id == account.id).order_by(PaperTradingSession.id.desc()))
        if not trading: trading = PaperTradingSession(account_id=account.id); self.session.add(trading); self.session.flush()
        return trading
    def notify(self, event, message, level="INFO"):
        self.session.add(PaperNotification(account_id=self.account().id, event=event, level=level, message=message))
    def start(self, universe="NIFTY50", strategy_name="EMA crossover", interval_seconds=300):
        state = self.state(); state.status, state.universe, state.strategy_name, state.interval_seconds, state.started_at = "RUNNING", universe, strategy_name, interval_seconds, datetime.now(timezone.utc); self.notify("TRADING_STARTED", "Paper trading started with simulated or configured paper-market data"); return state
    def pause(self): self.state().status = "PAUSED"; self.notify("TRADING_PAUSED", "Paper trading paused")
    def resume(self):
        if self._control(self.account()).kill_switch: raise RiskViolation("Kill switch is active")
        self.state().status = "RUNNING"; self.notify("TRADING_RESUMED", "Paper trading resumed")
    def stop(self): self.state().status = "STOPPED"; self.notify("TRADING_STOPPED", "Paper trading stopped; open positions remain open")
    def execute_signal(self, signal):
        account, control, state = self.account(), self._control(self.account()), self.state()
        if state.status != "RUNNING": raise RiskViolation("Paper session is not running")
        if control.kill_switch: raise RiskViolation("Paper trading kill switch is active")
        if signal.action != "BUY": raise RiskViolation("Only validated BUY entries are accepted by this long-only paper session")
        if control.require_stop_loss and not signal.stop_loss: raise RiskViolation("Stop-loss is required")
        if not signal.risk_reward or signal.risk_reward < control.min_risk_reward: raise RiskViolation("Signal risk/reward is below configured minimum")
        if self.session.scalar(select(PaperExecution).where(PaperExecution.symbol == signal.symbol, PaperExecution.candle_timestamp == signal.candle_timestamp, PaperExecution.strategy_name == signal.strategy_name)):
            raise RiskViolation("Duplicate paper execution prevented")
        quote = self.provider.quote(signal.symbol)
        if not quote.updated_at or (datetime.now(quote.updated_at.tzinfo) - quote.updated_at).total_seconds() > state.interval_seconds * 2: raise ProviderUnavailable("Market data is stale; simulated fill rejected")
        quantity = int(min(account.cash_balance * control.max_allocation_pct / 100, account.cash_balance) // quote.ltp)
        if quantity <= 0: raise RiskViolation("Insufficient virtual balance")
        order = OrderManager(self.session, self.adapter).place(account.id, OrderRequest(signal.symbol, OrderSide.BUY, OrderType.MARKET, quantity))
        self.session.add(PaperExecution(order_id=order.id, symbol=signal.symbol, strategy_name=signal.strategy_name, candle_timestamp=signal.candle_timestamp, requested_price=signal.price, execution_price=order.average_fill_price, data_source=signal.source))
        control_row = self.session.scalar(select(PaperPositionControl).where(PaperPositionControl.account_id == account.id, PaperPositionControl.symbol == signal.symbol))
        if control_row: control_row.stop_loss, control_row.target_price = signal.stop_loss, signal.target_price
        else: self.session.add(PaperPositionControl(account_id=account.id, symbol=signal.symbol, strategy_name=signal.strategy_name, stop_loss=signal.stop_loss, target_price=signal.target_price))
        self.notify("ORDER_EXECUTED", f"Simulated BUY {quantity} {signal.symbol} at {order.average_fill_price:.2f}"); self.snapshot(); return order
    def monitor_positions(self):
        account = self.account(); manager = OrderManager(self.session, self.adapter)
        for position in self.session.scalars(select(Position).where(Position.account_id == account.id, Position.quantity > 0)):
            control = self.session.scalar(select(PaperPositionControl).where(PaperPositionControl.account_id == account.id, PaperPositionControl.symbol == position.symbol))
            if not control: continue
            price = self.provider.quote(position.symbol).ltp
            if price <= control.stop_loss or price >= control.target_price:
                manager.place(account.id, OrderRequest(position.symbol, OrderSide.SELL, OrderType.MARKET, position.quantity)); reason = "STOP_LOSS_TRIGGERED" if price <= control.stop_loss else "TARGET_ACHIEVED"; self.notify(reason, f"Simulated exit {position.symbol} at {price:.2f}"); self.session.delete(control)
        self.snapshot()
    def scan_and_execute(self, symbols: list[str]):
        """Run a paper scan from the active provider; failures stay isolated per symbol."""
        if self.state().status != "RUNNING": return {}
        config, engine, results = StrategyManager(self.session).get_or_create(), StrategyEngine(self.session), {}
        end = datetime.now().astimezone(); start = end - timedelta(days=5)
        for symbol in symbols:
            try:
                candles = self.provider.candles(symbol, config.timeframe, start, end)
                signal = engine.evaluate(symbol, candles, config, self.provider.mode.value)
                results[symbol] = signal.action
                if signal.action == "BUY":
                    try: self.execute_signal(signal)
                    except (RiskViolation, ProviderUnavailable) as error: self.notify("ORDER_REJECTED", f"{symbol}: {error}", "WARNING")
            except Exception as error:
                self.notify("MARKET_DATA_UNAVAILABLE", f"{symbol}: {error}", "WARNING"); results[symbol] = "ERROR"
        self.monitor_positions(); return results
    def snapshot(self):
        account = self.account(); summary = PortfolioManager(self.session, self.adapter).summary(account); self.session.add(PortfolioSnapshot(account_id=account.id, equity=summary.total_value, available_cash=summary.available_balance, unrealised_pnl=summary.unrealised_pnl, realised_pnl=summary.realised_pnl)); return summary
    def dashboard(self):
        summary = self.snapshot(); account = self.account(); positions = list(self.session.scalars(select(Position).where(Position.account_id == account.id, Position.quantity != 0))); trades = list(self.session.scalars(select(TradeHistory).where(TradeHistory.account_id == account.id))); wins = len([t for t in trades if t.realised_pnl > 0]); losses = len([t for t in trades if t.realised_pnl < 0]); return {"state": self.state(), "summary": summary, "positions": positions, "total_trades": len(trades), "winning_trades": wins, "losing_trades": losses, "control": self._control(account)}
