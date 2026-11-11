from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.exceptions import RiskViolation
from backend.database.models import DailyPerformance, Order, OrderStatus, Position, RiskSetting, TradingAccount
from backend.providers.base_provider import MarketDataProvider
from backend.schemas.orders import OrderRequest


class RiskManager:
    def __init__(self, session: Session, provider: MarketDataProvider): self.session, self.provider = session, provider

    def validate(self, account: TradingAccount, request: OrderRequest) -> None:
        settings = self.session.get(RiskSetting, account.id)
        if not account.is_paper: raise RiskViolation("Only paper accounts are supported")
        if not account.trading_enabled or settings.emergency_shutdown: raise RiskViolation("Trading is disabled by the risk control")
        price = request.limit_price if request.order_type.value == "LIMIT" else self.provider.quote(request.symbol).price
        notional = request.quantity * price
        if notional > settings.max_position_size: raise RiskViolation("Order exceeds maximum position size")
        if request.side.value == "BUY" and notional > account.cash_balance: raise RiskViolation("Insufficient paper balance")
        open_positions = self.session.scalar(select(func.count(Position.id)).where(Position.account_id == account.id, Position.quantity != 0)) or 0
        existing = self.session.scalar(select(Position).where(Position.account_id == account.id, Position.symbol == request.symbol))
        if request.side.value == "BUY" and (not existing or existing.quantity == 0) and open_positions >= settings.max_open_positions: raise RiskViolation("Maximum open positions reached")
        day_start = datetime.combine(date.today(), datetime.min.time(), tzinfo=timezone.utc)
        trade_count = self.session.scalar(select(func.count(Order.id)).where(Order.account_id == account.id, Order.created_at >= day_start, Order.status.in_([OrderStatus.OPEN, OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]))) or 0
        if trade_count >= settings.max_trades_per_day: raise RiskViolation("Maximum trades per day reached")
        daily = self.session.scalar(select(DailyPerformance).where(DailyPerformance.account_id == account.id, DailyPerformance.trade_date == date.today().isoformat()))
        if daily and daily.daily_pnl <= -settings.max_daily_loss: raise RiskViolation("Daily loss limit reached")
        position_value = self.session.scalar(select(func.sum(func.abs(Position.quantity) * Position.average_entry_price)).where(Position.account_id == account.id)) or 0.0
        if request.side.value == "BUY" and (position_value + notional) / account.initial_capital * 100 > settings.max_capital_utilisation_pct: raise RiskViolation("Capital utilisation limit exceeded")
        duplicate = self.session.scalar(select(Order).where(Order.account_id == account.id, Order.symbol == request.symbol, Order.side == request.side, Order.status.in_([OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED])))
        if duplicate: raise RiskViolation("Duplicate active order prevented")
