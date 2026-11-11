from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class OrderSide(str, Enum): BUY = "BUY"; SELL = "SELL"
class OrderType(str, Enum): MARKET = "MARKET"; LIMIT = "LIMIT"
class OrderStatus(str, Enum): PENDING = "PENDING"; OPEN = "OPEN"; PARTIALLY_FILLED = "PARTIALLY_FILLED"; FILLED = "FILLED"; CANCELLED = "CANCELLED"; REJECTED = "REJECTED"


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class User(Base, Timestamped):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    accounts: Mapped[list["TradingAccount"]] = relationship(back_populates="user")


class TradingAccount(Base, Timestamped):
    __tablename__ = "trading_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(80), default="Paper Trading")
    initial_capital: Mapped[float] = mapped_column(Float, default=100000.0)
    cash_balance: Mapped[float] = mapped_column(Float, default=100000.0)
    is_paper: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    trading_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    user: Mapped[User] = relationship(back_populates="accounts")
    portfolio: Mapped["Portfolio"] = relationship(back_populates="account", uselist=False)
    orders: Mapped[list["Order"]] = relationship(back_populates="account")
    positions: Mapped[list["Position"]] = relationship(back_populates="account")


class Portfolio(Base, Timestamped):
    __tablename__ = "portfolios"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("trading_accounts.id"), unique=True)
    realised_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    account: Mapped[TradingAccount] = relationship(back_populates="portfolio")


class Order(Base, Timestamped):
    __tablename__ = "orders"
    __table_args__ = (Index("ix_orders_account_status", "account_id", "status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("trading_accounts.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(30), index=True)
    side: Mapped[OrderSide] = mapped_column(SAEnum(OrderSide))
    order_type: Mapped[OrderType] = mapped_column(SAEnum(OrderType))
    quantity: Mapped[int] = mapped_column(Integer)
    filled_quantity: Mapped[int] = mapped_column(Integer, default=0)
    limit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_fill_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[OrderStatus] = mapped_column(SAEnum(OrderStatus), default=OrderStatus.PENDING, index=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account: Mapped[TradingAccount] = relationship(back_populates="orders")


class Position(Base, Timestamped):
    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("account_id", "symbol", name="uq_position_account_symbol"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("trading_accounts.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(30), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    average_entry_price: Mapped[float] = mapped_column(Float, default=0.0)
    realised_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    account: Mapped[TradingAccount] = relationship(back_populates="positions")


class TradeHistory(Base, Timestamped):
    __tablename__ = "trade_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("trading_accounts.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(30), index=True)
    side: Mapped[OrderSide] = mapped_column(SAEnum(OrderSide))
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)
    realised_pnl: Mapped[float] = mapped_column(Float, default=0.0)


class TradingSignal(Base, Timestamped):
    __tablename__ = "trading_signals"
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(30), index=True)
    signal: Mapped[str] = mapped_column(String(12))
    entry_price: Mapped[float] = mapped_column(Float)
    target_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Strategy(Base, Timestamped):
    __tablename__ = "strategies"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    trades: Mapped[int] = mapped_column(Integer, default=0)
    profit_factor: Mapped[float] = mapped_column(Float, default=0.0)


class RiskSetting(Base, Timestamped):
    __tablename__ = "risk_settings"
    account_id: Mapped[int] = mapped_column(ForeignKey("trading_accounts.id"), primary_key=True)
    max_risk_per_trade_pct: Mapped[float] = mapped_column(Float, default=2.0)
    max_daily_loss: Mapped[float] = mapped_column(Float, default=5000.0)
    max_open_positions: Mapped[int] = mapped_column(Integer, default=8)
    max_trades_per_day: Mapped[int] = mapped_column(Integer, default=25)
    max_capital_utilisation_pct: Mapped[float] = mapped_column(Float, default=75.0)
    max_position_size: Mapped[float] = mapped_column(Float, default=50000.0)
    emergency_shutdown: Mapped[bool] = mapped_column(Boolean, default=False)


class DailyPerformance(Base, Timestamped):
    __tablename__ = "daily_performance"
    __table_args__ = (UniqueConstraint("account_id", "trade_date", name="uq_daily_performance"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("trading_accounts.id"), index=True)
    trade_date: Mapped[str] = mapped_column(String(10), index=True)
    equity: Mapped[float] = mapped_column(Float)
    daily_pnl: Mapped[float] = mapped_column(Float, default=0.0)


class SystemLog(Base, Timestamped):
    __tablename__ = "system_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    level: Mapped[str] = mapped_column(String(16), index=True)
    event: Mapped[str] = mapped_column(String(120), index=True)
    message: Mapped[str] = mapped_column(Text)
