from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.exceptions import InvalidOrderState, NotFoundError
from backend.core.logger import get_logger
from backend.database.models import DailyPerformance, Order, OrderStatus, OrderType, Portfolio, Position, TradeHistory, TradingAccount
from backend.database.repositories import record_system_log
from backend.providers.base_provider import MarketDataProvider
from backend.schemas.orders import OrderRequest
from backend.trading.risk_manager import RiskManager


class OrderManager:
    def __init__(self, session: Session, provider: MarketDataProvider): self.session, self.provider, self.logger = session, provider, get_logger("orbit.orders")

    def place(self, account_id: int, request: OrderRequest) -> Order:
        request.validate()
        account = self.session.get(TradingAccount, account_id)
        if not account: raise NotFoundError("Trading account not found")
        RiskManager(self.session, self.provider).validate(account, request)
        order = Order(account_id=account_id, symbol=request.symbol.upper(), side=request.side, order_type=request.order_type, quantity=request.quantity, limit_price=request.limit_price, status=OrderStatus.OPEN)
        self.session.add(order); self.session.flush()
        record_system_log(self.session, "INFO", "order_opened", f"Paper {order.side.value} order {order.id} opened for {order.symbol}")
        if request.order_type == OrderType.MARKET: self.fill(order.id, request.quantity)
        return order

    def cancel(self, order_id: int) -> Order:
        order = self.session.get(Order, order_id)
        if not order: raise NotFoundError("Order not found")
        if order.status not in (OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED): raise InvalidOrderState("Order cannot be cancelled")
        order.status = OrderStatus.CANCELLED
        record_system_log(self.session, "INFO", "order_cancelled", f"Paper order {order.id} cancelled")
        return order

    def fill(self, order_id: int, quantity: int, price: float | None = None) -> Order:
        order = self.session.get(Order, order_id)
        if not order: raise NotFoundError("Order not found")
        if order.status not in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED): raise InvalidOrderState("Order cannot be filled")
        remaining = order.quantity - order.filled_quantity
        if quantity <= 0 or quantity > remaining: raise InvalidOrderState("Invalid fill quantity")
        fill_price = price if price is not None else self.provider.quote(order.symbol).price
        old_value = (order.average_fill_price or 0) * order.filled_quantity
        order.filled_quantity += quantity
        order.average_fill_price = (old_value + fill_price * quantity) / order.filled_quantity
        order.status = OrderStatus.FILLED if order.filled_quantity == order.quantity else OrderStatus.PARTIALLY_FILLED
        self._apply_position(order, quantity, fill_price)
        record_system_log(self.session, "INFO", "order_filled", f"Paper order {order.id} filled {quantity} {order.symbol} at {fill_price:.2f}")
        self.logger.info("paper_order_filled order_id=%s symbol=%s quantity=%s", order.id, order.symbol, quantity)
        return order

    def _apply_position(self, order: Order, quantity: int, price: float) -> None:
        account = self.session.get(TradingAccount, order.account_id)
        position = self.session.query(Position).filter_by(account_id=account.id, symbol=order.symbol).one_or_none()
        if not position:
            position = Position(account_id=account.id, symbol=order.symbol); self.session.add(position); self.session.flush()
        signed = quantity if order.side.value == "BUY" else -quantity
        prior_qty, realised = position.quantity, 0.0
        if prior_qty == 0 or (prior_qty > 0 and signed > 0) or (prior_qty < 0 and signed < 0):
            combined = prior_qty + signed
            position.average_entry_price = ((abs(prior_qty) * position.average_entry_price) + (abs(signed) * price)) / abs(combined)
        else:
            closing = min(abs(prior_qty), abs(signed))
            realised = (price - position.average_entry_price) * closing * (1 if prior_qty > 0 else -1)
            if abs(signed) > abs(prior_qty): position.average_entry_price = price
            elif abs(signed) == abs(prior_qty): position.average_entry_price = 0.0
        position.quantity = prior_qty + signed
        position.realised_pnl += realised
        portfolio = self.session.get(Portfolio, account.id); portfolio.realised_pnl += realised
        account.cash_balance -= signed * price
        self.session.add(TradeHistory(account_id=account.id, order_id=order.id, symbol=order.symbol, side=order.side, quantity=quantity, price=price, realised_pnl=realised))
        positions = self.session.scalars(select(Position).where(Position.account_id == account.id)).all()
        equity = account.cash_balance + sum(self.provider.quote(item.symbol).price * item.quantity for item in positions)
        today = date.today().isoformat()
        performance = self.session.scalar(select(DailyPerformance).where(DailyPerformance.account_id == account.id, DailyPerformance.trade_date == today))
        if performance:
            performance.equity, performance.daily_pnl = equity, equity - account.initial_capital
        else:
            self.session.add(DailyPerformance(account_id=account.id, trade_date=today, equity=equity, daily_pnl=equity - account.initial_capital))
