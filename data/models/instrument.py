from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.models import Base


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (UniqueConstraint("exchange", "trading_symbol", name="uq_exchange_symbol"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    trading_symbol: Mapped[str] = mapped_column(String(30), index=True)
    company_name: Mapped[str] = mapped_column(String(200))
    exchange: Mapped[str] = mapped_column(String(12), default="NSE")
    instrument_token: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    sector: Mapped[str] = mapped_column(String(100), default="Unclassified")
    instrument_type: Mapped[str] = mapped_column(String(20), default="EQ")
    universe: Mapped[str] = mapped_column(String(20), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
