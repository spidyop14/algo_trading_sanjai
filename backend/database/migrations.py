"""Lightweight initial migration for the SQLite-only Phase 2 environment."""
from sqlalchemy import inspect

from backend.database.connection import engine
from backend.database.models import Base
from data.models import Candle, Instrument  # noqa: F401 - registers market tables with metadata
from strategy.models import GeneratedSignal, StrategyConfiguration  # noqa: F401 - registers strategy tables
from backtesting.models import BacktestRun, BacktestTrade  # noqa: F401 - registers backtest tables
from paper_trading.models import PaperExecution, PaperNotification, PaperPositionControl, PaperRiskControl, PaperTradingSession, PortfolioSnapshot  # noqa: F401 - registers paper tables
from broker.models import BrokerConnection, BrokerOrderReference  # noqa: F401 - registers broker tables
from readiness.models import DryRunOrderIntent, ReadinessAuditLog, ReadinessState  # noqa: F401 - registers readiness tables


def migrate() -> None:
    """Create all current schema objects; later production migrations can use Alembic."""
    Base.metadata.create_all(engine)


def schema_is_ready() -> bool:
    return {"users", "trading_accounts", "orders", "positions"}.issubset(set(inspect(engine).get_table_names()))
