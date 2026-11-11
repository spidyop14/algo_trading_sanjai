from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.database.models import Base

class ReadinessState(Base):
    __tablename__ = "readiness_state"
    account_id: Mapped[int] = mapped_column(ForeignKey("trading_accounts.id"), primary_key=True)
    emergency_stop: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class DryRunOrderIntent(Base):
    __tablename__ = "dry_run_order_intents"
    __table_args__ = (UniqueConstraint("symbol", "strategy_name", "candle_timestamp", name="uq_dry_run_intent"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("trading_accounts.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(30), index=True)
    strategy_name: Mapped[str] = mapped_column(String(100))
    side: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[int] = mapped_column(Integer)
    entry_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    target_price: Mapped[float] = mapped_column(Float)
    estimated_costs: Mapped[float] = mapped_column(Float)
    risk_status: Mapped[str] = mapped_column(String(16))
    candle_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    data_source: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default="DRY_RUN_NOT_SENT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class ReadinessAuditLog(Base):
    __tablename__ = "readiness_audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("trading_accounts.id"), index=True)
    event: Mapped[str] = mapped_column(String(60), index=True)
    level: Mapped[str] = mapped_column(String(12))
    details: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
