from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.database.models import Base

class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_name: Mapped[str] = mapped_column(String(100))
    symbols: Mapped[str] = mapped_column(Text)
    timeframe: Mapped[str] = mapped_column(String(8))
    start_date: Mapped[str] = mapped_column(String(32))
    end_date: Mapped[str] = mapped_column(String(32))
    initial_capital: Mapped[float] = mapped_column(Float)
    final_capital: Mapped[float] = mapped_column(Float)
    data_source: Mapped[str] = mapped_column(String(20))
    assumptions_json: Mapped[str] = mapped_column(Text)
    metrics_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class BacktestTrade(Base):
    __tablename__ = "backtest_trades"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(30), index=True)
    strategy_name: Mapped[str] = mapped_column(String(100))
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    exit_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[float] = mapped_column(Float)
    quantity: Mapped[int] = mapped_column(Integer)
    gross_pnl: Mapped[float] = mapped_column(Float)
    charges: Mapped[float] = mapped_column(Float)
    net_pnl: Mapped[float] = mapped_column(Float)
    exit_reason: Mapped[str] = mapped_column(String(30))
    holding_minutes: Mapped[float] = mapped_column(Float)
