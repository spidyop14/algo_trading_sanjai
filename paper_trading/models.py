from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.database.models import Base

class PaperTradingSession(Base):
    __tablename__ = "paper_trading_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("trading_accounts.id"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="STOPPED", index=True)
    universe: Mapped[str] = mapped_column(String(30), default="NIFTY50")
    strategy_name: Mapped[str] = mapped_column(String(100), default="EMA crossover")
    interval_seconds: Mapped[int] = mapped_column(Integer, default=300)
    configuration_json: Mapped[str] = mapped_column(Text, default="{}")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class PaperRiskControl(Base):
    __tablename__ = "paper_risk_controls"
    account_id: Mapped[int] = mapped_column(ForeignKey("trading_accounts.id"), primary_key=True)
    max_allocation_pct: Mapped[float] = mapped_column(Float, default=20.0)
    max_consecutive_losses: Mapped[int] = mapped_column(Integer, default=3)
    require_stop_loss: Mapped[bool] = mapped_column(Boolean, default=True)
    min_risk_reward: Mapped[float] = mapped_column(Float, default=1.5)
    kill_switch: Mapped[bool] = mapped_column(Boolean, default=False)

class PaperPositionControl(Base):
    __tablename__ = "paper_position_controls"
    __table_args__ = (UniqueConstraint("account_id", "symbol", name="uq_paper_position_control"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("trading_accounts.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(30), index=True)
    strategy_name: Mapped[str] = mapped_column(String(100))
    stop_loss: Mapped[float] = mapped_column(Float)
    target_price: Mapped[float] = mapped_column(Float)

class PaperExecution(Base):
    __tablename__ = "paper_executions"
    __table_args__ = (UniqueConstraint("symbol", "candle_timestamp", "strategy_name", name="uq_paper_execution_signal"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(30), index=True)
    strategy_name: Mapped[str] = mapped_column(String(100))
    candle_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    requested_price: Mapped[float] = mapped_column(Float)
    execution_price: Mapped[float] = mapped_column(Float)
    data_source: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class PaperNotification(Base):
    __tablename__ = "paper_notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("trading_accounts.id"), index=True)
    event: Mapped[str] = mapped_column(String(50), index=True)
    level: Mapped[str] = mapped_column(String(12))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("trading_accounts.id"), index=True)
    equity: Mapped[float] = mapped_column(Float)
    available_cash: Mapped[float] = mapped_column(Float)
    unrealised_pnl: Mapped[float] = mapped_column(Float)
    realised_pnl: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
