from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.database.models import Base


class GeneratedSignal(Base):
    __tablename__ = "generated_signals"
    __table_args__ = (UniqueConstraint("symbol", "candle_timestamp", "strategy_name", name="uq_strategy_signal_candle"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(30), index=True)
    exchange: Mapped[str] = mapped_column(String(12), default="NSE")
    action: Mapped[str] = mapped_column(String(12), index=True)
    classification: Mapped[str] = mapped_column(String(12))
    score: Mapped[int] = mapped_column(Integer)
    reference_price: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    target_price: Mapped[float] = mapped_column(Float)
    risk_reward: Mapped[float] = mapped_column(Float)
    strategy_name: Mapped[str] = mapped_column(String(100), index=True)
    data_source: Mapped[str] = mapped_column(String(16))
    candle_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    details_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
