from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from backend.database.models import Base, Position
from data.providers.simulated_provider import SimulatedMarketDataProvider
from paper_trading.models import PaperExecution, PaperPositionControl, PaperTradingSession
from paper_trading.scheduler import PaperTradingScheduler
from paper_trading.service import PaperTradingService
from strategy.signal_generator import Signal

IST = ZoneInfo("Asia/Kolkata")
@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine); db = sessionmaker(bind=engine)(); yield db; db.close()
def signal(symbol="RELIANCE", rr=2): return Signal(symbol, "BUY", "STRONG", 100, 2948.4, 2900, 3045, rr, "EMA crossover", "SIMULATION", datetime(2026, 1, 5, 10, 0, tzinfo=IST), {}, {})

def test_session_lifecycle_and_paper_execution(session):
    service = PaperTradingService(session, SimulatedMarketDataProvider()); service.start(interval_seconds=60)
    order = service.execute_signal(signal())
    assert order.average_fill_price > 0
    assert service.state().status == "RUNNING"
    assert session.scalar(select(PaperExecution)) is not None
    assert session.scalar(select(Position)).quantity > 0
    service.pause(); assert service.state().status == "PAUSED"; service.resume(); service.stop(); assert service.state().status == "STOPPED"

def test_duplicate_kill_switch_and_risk_rejections(session):
    service = PaperTradingService(session, SimulatedMarketDataProvider()); service.start(); service.execute_signal(signal())
    with pytest.raises(Exception, match="Duplicate") : service.execute_signal(signal())
    control = service.dashboard()["control"]; control.kill_switch = True
    with pytest.raises(Exception, match="kill switch"): service.execute_signal(signal("HDFCBANK"))

def test_stop_and_target_monitoring(session):
    service = PaperTradingService(session, SimulatedMarketDataProvider()); service.start(); service.execute_signal(signal())
    position = session.scalar(select(Position)); guard = session.scalar(select(PaperPositionControl)); guard.target_price = 1
    service.monitor_positions()
    assert position.quantity == 0 and session.scalar(select(PaperPositionControl)) is None

def test_scheduler_respects_market_calendar_without_running_process():
    calls = []
    class Closed: 
        def is_open(self): return False
    scheduler = PaperTradingScheduler(lambda: calls.append(1), interval_seconds=1, calendar=Closed())
    scheduler._loop = lambda: None
    assert scheduler.start() is True
    scheduler.stop(); assert calls == []
