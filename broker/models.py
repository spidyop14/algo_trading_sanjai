from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.database.models import Base

class BrokerConnection(Base):
    __tablename__ = "broker_connections"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("trading_accounts.id"), unique=True, index=True)
    broker_name: Mapped[str] = mapped_column(String(40), default="ZERODHA")
    status: Mapped[str] = mapped_column(String(32), default="DISCONNECTED")
    encrypted_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    profile_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class BrokerOrderReference(Base):
    __tablename__ = "broker_order_references"
    __table_args__ = (UniqueConstraint("broker_order_id", name="uq_broker_order_reference"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    local_order_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    broker_order_id: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
