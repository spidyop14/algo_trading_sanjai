from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.database.models import Base


class StrategyConfiguration(Base):
    __tablename__ = "strategy_configurations"
    __table_args__ = (UniqueConstraint("name", name="uq_strategy_configuration_name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    timeframe: Mapped[str] = mapped_column(String(8), default="5m")
    ema_fast: Mapped[int] = mapped_column(Integer, default=9)
    ema_slow: Mapped[int] = mapped_column(Integer, default=21)
    rsi_period: Mapped[int] = mapped_column(Integer, default=14)
    rsi_bullish: Mapped[float] = mapped_column(Float, default=55.0)
    rsi_bearish: Mapped[float] = mapped_column(Float, default=45.0)
    macd_fast: Mapped[int] = mapped_column(Integer, default=12)
    macd_slow: Mapped[int] = mapped_column(Integer, default=26)
    macd_signal: Mapped[int] = mapped_column(Integer, default=9)
    volume_multiple: Mapped[float] = mapped_column(Float, default=1.0)
    atr_period: Mapped[int] = mapped_column(Integer, default=14)
    atr_multiplier: Mapped[float] = mapped_column(Float, default=1.5)
    risk_reward: Mapped[float] = mapped_column(Float, default=2.0)
    min_signal_score: Mapped[int] = mapped_column(Integer, default=80)
    stop_mode: Mapped[str] = mapped_column(String(12), default="ATR")
    fixed_stop_pct: Mapped[float] = mapped_column(Float, default=1.0)
    enabled_indicators: Mapped[str] = mapped_column(Text, default="EMA,RSI,MACD,VOLUME,TREND")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
