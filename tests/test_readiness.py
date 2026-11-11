from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from backend.database.models import Base
from broker.models import BrokerConnection
from readiness.models import DryRunOrderIntent, ReadinessAuditLog
from readiness.service import ReadinessService
from strategy.signal_generator import Signal

IST = ZoneInfo("Asia/Kolkata")
class MockBroker:
    def __init__(self, session): self.session=session
    def connection(self):
        item=self.session.scalar(select(BrokerConnection))
        if not item: item=BrokerConnection(account_id=1); self.session.add(item); self.session.flush()
        return item
@pytest.fixture()
def service():
    engine=create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine); session=sessionmaker(bind=engine)(); yield ReadinessService(session, MockBroker(session)); session.close()
def signal(): return Signal("RELIANCE","BUY","STRONG",95,100,98,104,2,"EMA crossover","SIMULATION",datetime(2026,1,5,10,tzinfo=IST),{}, {})
def test_preflight_reports_disabled_live_mode(service):
    result=service.preflight(); assert result["live_trading"]=="DISABLED" and result["execution_mode"]=="DRY_RUN" and service.session.scalar(select(ReadinessAuditLog)) is not None
def test_dry_run_intent_duplicate_and_emergency_stop(service):
    intent=service.create_intent(signal(),100000); assert intent.status=="DRY_RUN_NOT_SENT" and service.session.scalar(select(DryRunOrderIntent)) is not None
    with pytest.raises(ValueError,match="Duplicate"): service.create_intent(signal(),100000)
    service.emergency_stop(True)
    with pytest.raises(RuntimeError,match="Emergency"): service.create_intent(Signal("TCS","BUY","STRONG",95,100,98,104,2,"EMA crossover","SIMULATION",datetime(2026,1,5,11,tzinfo=IST),{}, {}),100000)
