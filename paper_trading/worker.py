from backend.database.connection import SessionLocal
from data.providers.simulated_provider import SimulatedMarketDataProvider
from paper_trading.service import PaperTradingService

UNIVERSES = {"NIFTY50": ["RELIANCE", "HDFCBANK", "INFY", "TCS", "ICICIBANK", "SBIN", "TATAMOTORS"]}

def scan_active_paper_session():
    """Scheduler entrypoint: opens its own transaction and only uses labelled simulation data."""
    session = SessionLocal()
    try:
        service = PaperTradingService(session, SimulatedMarketDataProvider()); state = service.state()
        if state.status == "RUNNING": service.scan_and_execute(UNIVERSES.get(state.universe, UNIVERSES["NIFTY50"]))
        session.commit()
    except Exception:
        session.rollback(); raise
    finally: session.close()
