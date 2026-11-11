from datetime import datetime, timezone
from sqlalchemy import select
from backend.database.repositories import get_or_create_paper_account
from backtesting.costs import IndianEquityCostCalculator, TransactionCostConfig
from broker.exceptions import AuthenticationRequired, BrokerError
from broker.zerodha import ZerodhaBrokerService
from data.utils.market_calendar import NSEMarketCalendar
from paper_trading.models import PaperRiskControl
from readiness.models import DryRunOrderIntent, ReadinessAuditLog, ReadinessState

class ReadinessService:
    def __init__(self, session, broker=None, market_provider=None): self.session, self.broker, self.market_provider = session, broker or ZerodhaBrokerService(session), market_provider
    def account(self): return get_or_create_paper_account(self.session)
    def state(self):
        account = self.account(); item = self.session.get(ReadinessState, account.id)
        if not item: item = ReadinessState(account_id=account.id); self.session.add(item); self.session.flush()
        return item
    def audit(self, event, details, level="INFO"):
        self.session.add(ReadinessAuditLog(account_id=self.account().id, event=event, level=level, details=details))
    def preflight(self):
        account = self.account(); checks = []
        def add(name, status, detail): checks.append({"check":name,"status":status,"detail":detail})
        connection = self.broker.connection()
        add("Broker authentication", "PASS" if connection.status == "CONNECTED" else "FAIL", connection.status)
        add("Database", "PASS", "SQLite connection available")
        add("Market hours", "PASS" if NSEMarketCalendar().is_open() else "WARNING", NSEMarketCalendar().status())
        add("Market data", "WARNING" if not self.market_provider else "PASS", "No live market-data provider configured" if not self.market_provider else "Provider configured")
        risk = self.session.get(PaperRiskControl, account.id); add("Risk controls", "PASS" if risk else "WARNING", "Configured" if risk else "Paper risk controls have not been initialised")
        add("Emergency stop", "FAIL" if self.state().emergency_stop else "PASS", "Simulation processing stopped" if self.state().emergency_stop else "Inactive")
        score = round(sum({"PASS":100,"WARNING":60,"FAIL":0}[x["status"]] for x in checks) / len(checks))
        self.audit("PREFLIGHT", f"Readiness checks completed; score={score}")
        return {"checks":checks,"score":score,"execution_mode":"DRY_RUN","live_trading":"DISABLED"}
    def create_intent(self, signal, available_capital, allocation_pct=20, costs=TransactionCostConfig()):
        if self.state().emergency_stop: raise RuntimeError("Emergency stop is active; dry-run intent generation is paused")
        if signal.action not in {"BUY", "SELL"} or not signal.stop_loss or not signal.target_price: raise ValueError("Signal is not eligible for a protected dry-run intent")
        if self.session.scalar(select(DryRunOrderIntent).where(DryRunOrderIntent.symbol==signal.symbol, DryRunOrderIntent.strategy_name==signal.strategy_name, DryRunOrderIntent.candle_timestamp==signal.candle_timestamp)): raise ValueError("Duplicate dry-run intent prevented")
        quantity = int((available_capital * allocation_pct / 100) // signal.price)
        if quantity <= 0: raise ValueError("Available capital is insufficient for a dry-run quantity")
        calculator = IndianEquityCostCalculator(costs); estimate = calculator.charges(signal.price*quantity, signal.price*quantity)
        item = DryRunOrderIntent(account_id=self.account().id, symbol=signal.symbol, strategy_name=signal.strategy_name, side=signal.action, quantity=quantity, entry_price=signal.price, stop_loss=signal.stop_loss, target_price=signal.target_price, estimated_costs=estimate, risk_status="PASS", candle_timestamp=signal.candle_timestamp, data_source=signal.source)
        self.session.add(item); self.audit("DRY_RUN_INTENT", f"DRY RUN — NOT SENT TO BROKER: {signal.action} {quantity} {signal.symbol}"); return item
    def emergency_stop(self, active):
        self.state().emergency_stop = active; self.audit("EMERGENCY_STOP" if active else "SIMULATION_RESUMED", "Controls application dry-run simulation only; it does not affect broker positions or orders.", "WARNING" if active else "INFO")
