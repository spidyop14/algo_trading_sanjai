from backend.database.connection import SessionLocal
from backend.database.migrations import migrate
from backend.database.repositories import get_or_create_paper_account
from backend.providers.simulated_provider import SimulatedNSEProvider
from backend.trading.order_manager import OrderManager
from data.services.instrument_service import InstrumentService
from pathlib import Path
from strategy.strategy_manager import StrategyManager


def bootstrap_paper_trading():
    migrate()
    session = SessionLocal()
    try:
        account = get_or_create_paper_account(session)
        instruments = InstrumentService(session)
        if not instruments.list():
            instruments.import_master(Path(__file__).resolve().parents[2] / "data" / "instruments" / "nse_universe.csv")
        StrategyManager(session).get_or_create()
        session.commit()
        return account.id
    finally:
        session.close()


def order_manager(session):
    return OrderManager(session, SimulatedNSEProvider())
